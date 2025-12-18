import os
import subprocess
from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename
import whisper
from pathlib import Path
import tempfile
import shutil

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'outputs'

# Ensure folders exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv', 'webm'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def convert_to_wav(video_path, output_wav):
    """Step 1: Extract audio from video to WAV format using ffmpeg"""
    try:
        cmd = [
            'ffmpeg', '-i', video_path,
            '-vn',  # No video
            '-acodec', 'pcm_s16le',  # PCM 16-bit
            '-ar', '16000',  # Sample rate
            '-ac', '1',  # Mono
            '-y',  # Overwrite
            output_wav
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return True, "Audio extracted successfully"
    except subprocess.CalledProcessError as e:
        return False, f"FFmpeg error: {e.stderr.decode()}"
    except Exception as e:
        return False, f"Error: {str(e)}"

def transcribe_audio(wav_path, model_name='base'):
    """Step 2: Use Whisper to transcribe audio"""
    try:
        model = whisper.load_model(model_name)
        result = model.transcribe(wav_path)
        return True, result
    except Exception as e:
        return False, f"Whisper error: {str(e)}"

def format_timestamp_srt(seconds):
    """Format seconds to SRT timestamp format"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def format_timestamp_vtt(seconds):
    """Format seconds to VTT timestamp format"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"

def generate_subtitles(transcription, output_path, format_type='srt'):
    """Step 3: Generate SRT or VTT subtitle file"""
    try:
        segments = transcription['segments']
        
        with open(output_path, 'w', encoding='utf-8') as f:
            if format_type == 'vtt':
                f.write('WEBVTT\n\n')
                for i, segment in enumerate(segments):
                    start = format_timestamp_vtt(segment['start'])
                    end = format_timestamp_vtt(segment['end'])
                    text = segment['text'].strip()
                    f.write(f"{start} --> {end}\n{text}\n\n")
            else:  # SRT
                for i, segment in enumerate(segments, 1):
                    start = format_timestamp_srt(segment['start'])
                    end = format_timestamp_srt(segment['end'])
                    text = segment['text'].strip()
                    f.write(f"{i}\n{start} --> {end}\n{text}\n\n")
        
        return True, f"{format_type.upper()} file generated successfully"
    except Exception as e:
        return False, f"Subtitle generation error: {str(e)}"

def burn_subtitles(video_path, subtitle_path, output_path):
    """Step 4: Burn subtitles into video using ffmpeg"""
    try:
        # Convert Windows path to ffmpeg format
        subtitle_path_ffmpeg = subtitle_path.replace('\\', '/').replace(':', '\\\\:')
        
        cmd = [
            'ffmpeg', '-i', video_path,
            '-vf', f"subtitles='{subtitle_path_ffmpeg}'",
            '-c:a', 'copy',
            '-y',
            output_path
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return True, "Subtitles burned successfully"
    except subprocess.CalledProcessError as e:
        return False, f"FFmpeg burn error: {e.stderr.decode()}"
    except Exception as e:
        return False, f"Error burning subtitles: {str(e)}"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process_video():
    """Main endpoint to process video through all 4 steps"""
    if 'video' not in request.files:
        return jsonify({'error': 'No video file provided'}), 400
    
    file = request.files['video']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type'}), 400
    
    subtitle_format = request.form.get('format', 'srt').lower()
    whisper_model = request.form.get('model', 'base')
    
    # Save uploaded video
    filename = secure_filename(file.filename)
    video_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(video_path)
    
    base_name = os.path.splitext(filename)[0]
    wav_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{base_name}.wav")
    subtitle_path = os.path.join(app.config['OUTPUT_FOLDER'], f"{base_name}.{subtitle_format}")
    output_video_path = os.path.join(app.config['OUTPUT_FOLDER'], f"{base_name}_subtitled.mp4")
    
    try:
        # Step 1: Extract audio
        success, message = convert_to_wav(video_path, wav_path)
        if not success:
            return jsonify({'error': message, 'step': 1}), 500
        
        # Step 2: Transcribe with Whisper
        success, result = transcribe_audio(wav_path, whisper_model)
        if not success:
            return jsonify({'error': result, 'step': 2}), 500
        
        # Step 3: Generate subtitles
        success, message = generate_subtitles(result, subtitle_path, subtitle_format)
        if not success:
            return jsonify({'error': message, 'step': 3}), 500
        
        # Step 4: Burn subtitles
        success, message = burn_subtitles(video_path, subtitle_path, output_video_path)
        if not success:
            return jsonify({'error': message, 'step': 4}), 500
        
        # Cleanup
        if os.path.exists(wav_path):
            os.remove(wav_path)
        if os.path.exists(video_path):
            os.remove(video_path)
        
        return jsonify({
            'success': True,
            'message': 'Video processed successfully',
            'subtitle_file': f"{base_name}.{subtitle_format}",
            'output_video': f"{base_name}_subtitled.mp4"
        })
    
    except Exception as e:
        return jsonify({'error': f'Unexpected error: {str(e)}'}), 500

@app.route('/download/<filename>')
def download_file(filename):
    """Download processed files"""
    file_path = os.path.join(app.config['OUTPUT_FOLDER'], secure_filename(filename))
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    return jsonify({'error': 'File not found'}), 404

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

