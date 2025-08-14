"""E2B MCP tools implementation for sandboxed code execution"""

from typing import Dict, Any, Optional, List
from e2b import Sandbox
from utils.logger import setup_logger
from utils.config import config
import asyncio
import re

logger = setup_logger(__name__)


class E2BTools:
    """MCP tools for E2B sandboxed code execution"""
    
    def __init__(self, conf: Any = None):
        self.config = conf or config
        
        if not self.config.e2b_api_key:
            logger.warning("E2B API key not configured")
    
    async def execute_github_repo(
        self,
        repo_url: str,
        template: str = "python3"
    ) -> Dict[str, Any]:
        """
        Clone and execute a GitHub repository in E2B sandbox
        
        Args:
            repo_url: GitHub repository URL
            template: E2B template to use (python3, node, etc.)
            
        Returns:
            Execution results
        """
        try:
            if not self.config.e2b_api_key:
                return {
                    "success": False,
                    "error": "E2B API key not configured. Please add E2B_API_KEY to .env"
                }
            
            # Parse repository info
            repo_info = self._parse_repo_url(repo_url)
            if not repo_info:
                return {
                    "success": False,
                    "error": f"Invalid GitHub URL: {repo_url}"
                }
            
            logger.info(f"Executing GitHub repo in E2B: {repo_info['full_name']}")
            
            # Create sandbox
            sandbox = Sandbox(template=template, api_key=self.config.e2b_api_key)
            
            try:
                # Clone repository
                clone_result = sandbox.run_code(f"""
import subprocess
import os

# Clone the repository
result = subprocess.run([
    'git', 'clone', '{repo_url}', '/tmp/repo'
], capture_output=True, text=True)

if result.returncode != 0:
    print(f"Clone failed: {{result.stderr}}")
else:
    print("Repository cloned successfully")
    
    # List repository contents
    os.chdir('/tmp/repo')
    contents = subprocess.run(['ls', '-la'], capture_output=True, text=True)
    print("Repository contents:")
    print(contents.stdout)
    
    # Look for common files
    important_files = []
    for file in ['README.md', 'requirements.txt', 'package.json', 'main.py', 'app.py', 'index.js']:
        if os.path.exists(file):
            important_files.append(file)
    
    print(f"Important files found: {{important_files}}")
""")
                
                setup_output = clone_result.stdout + (clone_result.stderr or "")
                
                # Try to run the project
                execution_result = await self._try_execute_project(sandbox, repo_info)
                
                # Get file contents for key files
                file_contents = await self._get_key_files(sandbox)
                
                return {
                    "success": True,
                    "repo_name": repo_info["repo"],
                    "repo_url": repo_url,
                    "template": template,
                    "setup_output": setup_output,
                    "execution_result": execution_result,
                    "file_contents": file_contents,
                    "sandbox_id": sandbox.id
                }
                
            finally:
                # Clean up
                sandbox.close()
                
        except Exception as e:
            logger.error(f"Error executing GitHub repo: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def execute_code_snippet(
        self,
        code: str,
        language: str = "python",
        description: str = ""
    ) -> Dict[str, Any]:
        """
        Execute a code snippet in E2B sandbox
        
        Args:
            code: Code to execute
            language: Programming language
            description: Description of what the code does
            
        Returns:
            Execution results
        """
        try:
            if not self.config.e2b_api_key:
                return {
                    "success": False,
                    "error": "E2B API key not configured"
                }
            
            # Map language to E2B template
            template_map = {
                "python": "python3",
                "javascript": "node",
                "typescript": "node",
                "bash": "bash",
                "go": "go",
                "rust": "rust"
            }
            
            template = template_map.get(language.lower(), "python3")
            
            logger.info(f"Executing {language} code in E2B")
            
            # Create sandbox
            sandbox = Sandbox(template=template, api_key=self.config.e2b_api_key)
            
            try:
                # Execute code
                result = sandbox.run_code(code)
                
                return {
                    "success": True,
                    "language": language,
                    "template": template,
                    "description": description,
                    "output": result.stdout,
                    "errors": result.stderr,
                    "exit_code": result.exit_code,
                    "execution_time": getattr(result, 'execution_time', None)
                }
                
            finally:
                sandbox.close()
                
        except Exception as e:
            logger.error(f"Error executing code snippet: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def analyze_and_run_project(
        self,
        repo_url: str,
        auto_install: bool = True
    ) -> Dict[str, Any]:
        """
        Analyze a GitHub project and automatically run it
        
        Args:
            repo_url: GitHub repository URL
            auto_install: Whether to automatically install dependencies
            
        Returns:
            Analysis and execution results
        """
        try:
            if not self.config.e2b_api_key:
                return {
                    "success": False,
                    "error": "E2B API key not configured"
                }
            
            repo_info = self._parse_repo_url(repo_url)
            if not repo_info:
                return {
                    "success": False,
                    "error": f"Invalid GitHub URL: {repo_url}"
                }
            
            logger.info(f"Analyzing and running project: {repo_info['full_name']}")
            
            # Determine the best template based on repo
            template = await self._detect_project_type(repo_url)
            
            sandbox = Sandbox(template=template, api_key=self.config.e2b_api_key)
            
            try:
                # Clone and analyze
                analysis = sandbox.run_code(f"""
import subprocess
import os
import json

# Clone repository
subprocess.run(['git', 'clone', '{repo_url}', '/tmp/repo'], 
               capture_output=True, text=True)
os.chdir('/tmp/repo')

# Analyze project structure
analysis = {{
    'project_type': 'unknown',
    'main_files': [],
    'dependencies': [],
    'has_readme': False,
    'has_tests': False
}}

# Check for different project types
if os.path.exists('requirements.txt'):
    analysis['project_type'] = 'python'
    with open('requirements.txt', 'r') as f:
        analysis['dependencies'] = f.read().splitlines()
elif os.path.exists('package.json'):
    analysis['project_type'] = 'node'
    try:
        with open('package.json', 'r') as f:
            pkg = json.loads(f.read())
            analysis['dependencies'] = list(pkg.get('dependencies', {{}}).keys())
    except:
        pass
elif os.path.exists('Cargo.toml'):
    analysis['project_type'] = 'rust'
elif os.path.exists('go.mod'):
    analysis['project_type'] = 'go'

# Find main files
for file in os.listdir('.'):
    if file.endswith(('.py', '.js', '.ts', '.go', '.rs')):
        analysis['main_files'].append(file)

analysis['has_readme'] = os.path.exists('README.md')
analysis['has_tests'] = any(os.path.exists(d) for d in ['tests', 'test', '__tests__'])

print(json.dumps(analysis, indent=2))
""")
                
                try:
                    project_analysis = eval(analysis.stdout.strip())
                except:
                    project_analysis = {"project_type": "unknown"}
                
                # Install dependencies if requested
                install_output = ""
                if auto_install:
                    install_output = await self._install_dependencies(sandbox, project_analysis)
                
                # Try to run the project
                run_output = await self._run_main_file(sandbox, project_analysis)
                
                return {
                    "success": True,
                    "repo_url": repo_url,
                    "analysis": project_analysis,
                    "install_output": install_output,
                    "run_output": run_output,
                    "template": template,
                    "sandbox_id": sandbox.id
                }
                
            finally:
                sandbox.close()
                
        except Exception as e:
            logger.error(f"Error analyzing project: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _try_execute_project(self, sandbox: Sandbox, repo_info: Dict) -> str:
        """Try to execute the project in various ways"""
        try:
            # Try common execution patterns
            execution_attempts = [
                "python main.py",
                "python app.py", 
                "python -m .",
                "npm start",
                "npm run dev",
                "cargo run",
                "go run .",
                "make run"
            ]
            
            results = []
            for cmd in execution_attempts:
                try:
                    result = sandbox.run_code(f"""
import subprocess
import os
os.chdir('/tmp/repo')

result = subprocess.run(['{cmd}'], shell=True, 
                       capture_output=True, text=True, timeout=10)
print(f"Command: {cmd}")
print(f"Exit code: {{result.returncode}}")
print(f"Output: {{result.stdout}}")
if result.stderr:
    print(f"Errors: {{result.stderr}}")
""")
                    if "Exit code: 0" in result.stdout:
                        results.append(f"✅ {cmd}: Success")
                        break
                    else:
                        results.append(f"❌ {cmd}: Failed")
                except:
                    results.append(f"⚠️ {cmd}: Timeout/Error")
            
            return "\n".join(results)
            
        except Exception as e:
            return f"Execution failed: {str(e)}"
    
    async def _get_key_files(self, sandbox: Sandbox) -> Dict[str, str]:
        """Get contents of key project files"""
        try:
            result = sandbox.run_code("""
import os
import json

os.chdir('/tmp/repo')
files_content = {}

key_files = ['README.md', 'main.py', 'app.py', 'package.json', 'requirements.txt']
for file in key_files:
    if os.path.exists(file):
        try:
            with open(file, 'r') as f:
                content = f.read()
                if len(content) > 2000:  # Limit size
                    content = content[:2000] + "... (truncated)"
                files_content[file] = content
        except:
            files_content[file] = "Could not read file"

print(json.dumps(files_content, indent=2))
""")
            
            try:
                return eval(result.stdout.strip())
            except:
                return {}
                
        except Exception as e:
            logger.warning(f"Could not get key files: {e}")
            return {}
    
    async def _detect_project_type(self, repo_url: str) -> str:
        """Detect the best E2B template for a repository"""
        # Simple heuristic based on repo URL/name
        repo_lower = repo_url.lower()
        
        if any(lang in repo_lower for lang in ['python', 'py', 'django', 'flask']):
            return "python3"
        elif any(lang in repo_lower for lang in ['node', 'js', 'react', 'vue', 'next']):
            return "node"
        elif 'rust' in repo_lower:
            return "rust"
        elif any(lang in repo_lower for lang in ['go', 'golang']):
            return "go"
        else:
            return "python3"  # Default
    
    async def _install_dependencies(self, sandbox: Sandbox, analysis: Dict) -> str:
        """Install project dependencies"""
        try:
            project_type = analysis.get('project_type', 'unknown')
            
            if project_type == 'python':
                result = sandbox.run_code("""
import subprocess
import os
os.chdir('/tmp/repo')

if os.path.exists('requirements.txt'):
    result = subprocess.run(['pip', 'install', '-r', 'requirements.txt'], 
                           capture_output=True, text=True)
    print(f"Pip install exit code: {result.returncode}")
    print(result.stdout)
    if result.stderr:
        print(f"Errors: {result.stderr}")
else:
    print("No requirements.txt found")
""")
                return result.stdout
                
            elif project_type == 'node':
                result = sandbox.run_code("""
import subprocess
import os
os.chdir('/tmp/repo')

if os.path.exists('package.json'):
    result = subprocess.run(['npm', 'install'], 
                           capture_output=True, text=True)
    print(f"NPM install exit code: {result.returncode}")
    print(result.stdout)
    if result.stderr:
        print(f"Errors: {result.stderr}")
else:
    print("No package.json found")
""")
                return result.stdout
            
            return "No dependency installation needed"
            
        except Exception as e:
            return f"Dependency installation failed: {str(e)}"
    
    async def _run_main_file(self, sandbox: Sandbox, analysis: Dict) -> str:
        """Try to run the main project file"""
        try:
            main_files = analysis.get('main_files', [])
            project_type = analysis.get('project_type', 'unknown')
            
            if not main_files:
                return "No main files found to execute"
            
            # Try to run the most likely main file
            for file in ['main.py', 'app.py', 'index.js', 'main.js']:
                if file in main_files:
                    if project_type == 'python':
                        cmd = f"python {file}"
                    elif project_type == 'node':
                        cmd = f"node {file}"
                    else:
                        continue
                    
                    result = sandbox.run_code(f"""
import subprocess
import os
os.chdir('/tmp/repo')

result = subprocess.run(['{cmd}'], shell=True,
                       capture_output=True, text=True, timeout=15)
print(f"Running: {cmd}")
print(f"Exit code: {{result.returncode}}")
print(f"Output: {{result.stdout}}")
if result.stderr:
    print(f"Errors: {{result.stderr}}")
""")
                    return result.stdout
            
            return "Could not determine how to run the project"
            
        except Exception as e:
            return f"Execution failed: {str(e)}"
    
    def _parse_repo_url(self, url: str) -> Optional[Dict[str, str]]:
        """Parse GitHub repository URL"""
        import re
        
        patterns = [
            r'github\.com[/:]([^/]+)/([^/\s]+?)(?:\.git)?(?:/.*)?$',
            r'raw\.githubusercontent\.com/([^/]+)/([^/]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                owner = match.group(1)
                repo = match.group(2).replace('.git', '')
                
                return {
                    "owner": owner,
                    "repo": repo,
                    "full_name": f"{owner}/{repo}"
                }
        
        return None