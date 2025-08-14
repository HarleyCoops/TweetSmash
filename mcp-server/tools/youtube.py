"""YouTube MCP tools implementation"""

from typing import Dict, Any, Optional
import re
import openai
from yt_dlp import YoutubeDL
from utils.logger import setup_logger
from utils.config import config
import tempfile
import os

logger = setup_logger(__name__)


class YouTubeTools:
    """MCP tools for YouTube video processing"""
    
    def __init__(self, conf: Any = None):
        self.config = conf or config
        
        # Initialize OpenAI client for transcription and summarization
        if self.config.openai_api_key:
            openai.api_key = self.config.openai_api_key
            self.openai_available = True
        else:
            logger.warning("OpenAI API key not configured, transcription will be limited")
            self.openai_available = False
        
        # Configure yt-dlp
        self.ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }
    
    async def transcribe_and_summarize(
        self,
        video_url: str,
        summary_style: str = "brief"
    ) -> Dict[str, Any]:
        """
        Transcribe and summarize a YouTube video
        
        Args:
            video_url: YouTube video URL
            summary_style: Style of summary (brief, detailed, action_items)
            
        Returns:
            Transcription and summary results
        """
        try:
            if not self.openai_available:
                return {
                    "success": False,
                    "error": "OpenAI API key not configured. Cannot transcribe video."
                }
            
            # Extract video ID and get metadata
            video_id = self._extract_video_id(video_url)
            if not video_id:
                return {
                    "success": False,
                    "error": f"Invalid YouTube URL: {video_url}"
                }
            
            logger.info(f"Processing YouTube video: {video_id}")
            
            # Get video metadata
            metadata = await self.get_video_metadata(video_url)
            if not metadata.get("success"):
                return metadata
            
            # Check video duration (limit to 1 hour for cost management)
            duration = metadata.get("duration", 0)
            if duration > 3600:
                return {
                    "success": False,
                    "error": f"Video too long ({duration}s). Maximum duration is 1 hour."
                }
            
            # Download audio
            audio_file = await self._download_audio(video_url)
            if not audio_file:
                return {
                    "success": False,
                    "error": "Failed to download audio from video"
                }
            
            try:
                # Transcribe using Whisper API
                logger.info("Transcribing audio with OpenAI Whisper...")
                with open(audio_file, 'rb') as f:
                    transcript_response = openai.Audio.transcribe(
                        model="whisper-1",
                        file=f,
                        response_format="text"
                    )
                
                transcript = transcript_response
                
                # Generate summary based on style
                summary = await self._generate_summary(transcript, summary_style, metadata)
                
                # Clean up temporary file
                os.unlink(audio_file)
                
                return {
                    "success": True,
                    "video_id": video_id,
                    "title": metadata.get("title"),
                    "channel": metadata.get("channel"),
                    "duration": duration,
                    "url": video_url,
                    "transcript": transcript,
                    "summary": summary,
                    "summary_style": summary_style,
                    "metadata": metadata
                }
                
            finally:
                # Ensure cleanup
                if os.path.exists(audio_file):
                    os.unlink(audio_file)
                    
        except Exception as e:
            logger.error(f"Error transcribing video: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_video_metadata(self, video_url: str) -> Dict[str, Any]:
        """
        Get metadata for a YouTube video
        
        Args:
            video_url: YouTube video URL
            
        Returns:
            Video metadata
        """
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
            }
            
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
                
                return {
                    "success": True,
                    "video_id": info.get('id'),
                    "title": info.get('title'),
                    "description": info.get('description', '')[:500],  # First 500 chars
                    "channel": info.get('uploader'),
                    "channel_id": info.get('uploader_id'),
                    "duration": info.get('duration'),
                    "view_count": info.get('view_count'),
                    "like_count": info.get('like_count'),
                    "upload_date": info.get('upload_date'),
                    "tags": info.get('tags', []),
                    "categories": info.get('categories', []),
                    "thumbnail": info.get('thumbnail'),
                    "url": video_url
                }
                
        except Exception as e:
            logger.error(f"Error getting video metadata: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _download_audio(self, video_url: str) -> Optional[str]:
        """
        Download audio from YouTube video
        
        Args:
            video_url: YouTube video URL
            
        Returns:
            Path to downloaded audio file
        """
        try:
            # Create temporary directory
            temp_dir = tempfile.mkdtemp()
            output_template = os.path.join(temp_dir, '%(title)s.%(ext)s')
            
            ydl_opts = self.ydl_opts.copy()
            ydl_opts['outtmpl'] = output_template
            
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=True)
                
                # Find the downloaded file
                base_filename = ydl.prepare_filename(info)
                audio_file = base_filename.rsplit('.', 1)[0] + '.mp3'
                
                if os.path.exists(audio_file):
                    logger.info(f"Audio downloaded: {audio_file}")
                    return audio_file
                else:
                    logger.error("Audio file not found after download")
                    return None
                    
        except Exception as e:
            logger.error(f"Error downloading audio: {e}")
            return None
    
    async def _generate_summary(
        self,
        transcript: str,
        style: str,
        metadata: Dict
    ) -> str:
        """
        Generate summary from transcript
        
        Args:
            transcript: Video transcript
            style: Summary style
            metadata: Video metadata
            
        Returns:
            Generated summary
        """
        try:
            # Prepare prompt based on style
            if style == "brief":
                prompt = f"""
                Summarize this YouTube video transcript in 3-5 bullet points.
                Video Title: {metadata.get('title')}
                
                Transcript:
                {transcript[:8000]}  # Limit for token management
                
                Provide a concise summary focusing on key points.
                """
            elif style == "detailed":
                prompt = f"""
                Create a detailed summary of this YouTube video transcript.
                Video Title: {metadata.get('title')}
                
                Transcript:
                {transcript[:8000]}
                
                Include:
                1. Main topic and purpose
                2. Key points discussed
                3. Important details or examples
                4. Conclusions or takeaways
                """
            elif style == "action_items":
                prompt = f"""
                Extract actionable items and key learnings from this YouTube video transcript.
                Video Title: {metadata.get('title')}
                
                Transcript:
                {transcript[:8000]}
                
                List:
                1. Action items or steps mentioned
                2. Key learnings or insights
                3. Resources or tools mentioned
                4. Next steps suggested
                """
            else:
                prompt = f"Summarize this transcript: {transcript[:8000]}"
            
            # Generate summary using GPT
            response = openai.ChatCompletion.create(
                model=self.config.openai_model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that creates concise, accurate summaries."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.7
            )
            
            summary = response.choices[0].message.content
            return summary
            
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return f"Summary generation failed: {str(e)}"
    
    def _extract_video_id(self, url: str) -> Optional[str]:
        """
        Extract YouTube video ID from URL
        
        Args:
            url: YouTube URL
            
        Returns:
            Video ID or None
        """
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([^&\n?]*)',
            r'youtube\.com\/v\/([^&\n?]*)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
    
    async def get_video_transcript(self, video_url: str) -> Dict[str, Any]:
        """
        Get just the transcript without summarization
        
        Args:
            video_url: YouTube video URL
            
        Returns:
            Transcript text
        """
        try:
            # First try to get YouTube's auto-generated captions
            video_id = self._extract_video_id(video_url)
            if not video_id:
                return {
                    "success": False,
                    "error": "Invalid YouTube URL"
                }
            
            # Try using youtube-transcript-api as fallback
            try:
                from youtube_transcript_api import YouTubeTranscriptApi
                
                transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
                transcript = " ".join([item['text'] for item in transcript_list])
                
                return {
                    "success": True,
                    "video_id": video_id,
                    "transcript": transcript,
                    "source": "youtube_captions"
                }
            except:
                # Fallback to Whisper if captions not available
                if self.openai_available:
                    result = await self.transcribe_and_summarize(
                        video_url,
                        summary_style="none"  # Skip summary
                    )
                    if result.get("success"):
                        return {
                            "success": True,
                            "video_id": video_id,
                            "transcript": result.get("transcript"),
                            "source": "whisper_api"
                        }
                
                return {
                    "success": False,
                    "error": "No captions available and OpenAI API not configured"
                }
                
        except Exception as e:
            logger.error(f"Error getting transcript: {e}")
            return {
                "success": False,
                "error": str(e)
            }