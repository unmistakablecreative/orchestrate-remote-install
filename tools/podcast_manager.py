import os
import re
import json
import argparse
import subprocess
from datetime import datetime

CHUNK_MINUTES = 10
CHUNK_START_SECONDS = 120
MIDROLL_TIMESTAMP_PATTERN = '\\[(\\d{2}):(\\d{2}):(\\d{2})\\]'
PODCAST_INDEX = 'data/podcast_index.json'
TRANSCRIPT_INDEX = 'data/transcript_index.json'
PODCAST_PREP_GUIDELINES = 'data/podcast_prep_guidelines.json'


def slugify(text):
    return text.lower().strip().replace('_', '-').replace(' ', '-')


def parse_timestamp(ts):
    match = re.match(MIDROLL_TIMESTAMP_PATTERN, ts)
    if not match:
        return None
    h, m, s = map(int, match.groups())
    return h * 3600 + m * 60 + s


def format_timestamp(seconds):
    """Convert seconds to [HH:MM:SS] format"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"[{h:02d}:{m:02d}:{s:02d}]"


def detect_silence_clusters(audio_file, start_range=1500, end_range=2400, noise_threshold=-30, min_duration=1.5):
    """
    Detect clusters of long silences in audio file using FFmpeg.

    Args:
        audio_file: Path to audio file
        start_range: Start of search range in seconds (default 25 min)
        end_range: End of search range in seconds (default 40 min)
        noise_threshold: Silence threshold in dB (default -30)
        min_duration: Minimum silence duration in seconds (default 1.5)

    Returns:
        List of silence clusters with timestamps
    """
    try:
        result = subprocess.run([
            'ffmpeg', '-i', audio_file,
            '-af', f'silencedetect=noise={noise_threshold}dB:d={min_duration}',
            '-f', 'null', '-'
        ], capture_output=True, text=True, timeout=300)

        # Parse silence markers (FFmpeg outputs to stderr)
        silences = []
        for line in result.stderr.split('\n'):
            if 'silence_start:' in line:
                start = float(line.split('silence_start:')[1].strip())
                silences.append({'start': start})
            elif 'silence_end:' in line and '|' in line:
                parts = line.split('|')
                end = float(parts[0].split('silence_end:')[1].strip())
                duration = float(parts[1].split('silence_duration:')[1].strip())
                if silences and 'end' not in silences[-1]:
                    silences[-1]['end'] = end
                    silences[-1]['duration'] = duration

        # Filter to target range and long silences
        filtered = [s for s in silences
                   if start_range <= s.get('start', 0) <= end_range
                   and s.get('duration', 0) >= min_duration]

        # Find clusters (multiple silences within 30s window)
        clusters = []
        for i, silence in enumerate(filtered):
            # Look ahead for nearby silences
            cluster_silences = [silence]
            for j in range(i + 1, len(filtered)):
                if filtered[j]['start'] - silence['start'] <= 30:
                    cluster_silences.append(filtered[j])
                else:
                    break

            if len(cluster_silences) >= 2:
                clusters.append({
                    'start': cluster_silences[0]['start'],
                    'end': cluster_silences[-1]['end'],
                    'silence_count': len(cluster_silences),
                    'silences': cluster_silences
                })

        return clusters

    except subprocess.TimeoutExpired:
        return {'status': 'error', 'message': 'FFmpeg timeout after 5 minutes'}
    except Exception as e:
        return {'status': 'error', 'message': f'FFmpeg error: {str(e)}'}


def find_speaker_transition(transcript_file, search_start, search_end, host_name='Srini Rao'):
    """
    Find speaker transition from guest to host in transcript.

    Returns the timestamp where the HOST starts speaking (midroll insertion point).

    Args:
        transcript_file: Path to transcript file
        search_start: Start time in seconds
        search_end: End time in seconds
        host_name: Name of host speaker (default 'Srini Rao')

    Returns:
        Dictionary with transition timestamp and context
    """
    try:
        with open(transcript_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        current_speaker = None
        current_line_start = None
        current_line_text = None

        for line in lines:
            # Extract timestamp
            ts_match = re.search(r'\[(\d{2}):(\d{2}):(\d{2})\]', line)
            if ts_match:
                h, m, s = map(int, ts_match.groups())
                timestamp = h * 3600 + m * 60 + s

                if timestamp < search_start:
                    continue
                if timestamp > search_end:
                    break

                # Check for speaker change
                speaker_match = re.search(r'\*\*([^:*]+):\*\*', line)
                if speaker_match:
                    speaker = normalize_speaker_name(speaker_match.group(1).strip())

                    # Guest → Host transition (FIRST occurrence only)
                    if current_speaker and current_speaker != host_name and speaker == host_name:
                        # Return HOST's start time (where midroll should go)
                        return {
                            'guest_end_time': current_line_start,  # Where guest's last line started
                            'guest_end_timestamp': format_timestamp(current_line_start),
                            'host_start_time': timestamp,  # Where YOU start speaking
                            'host_start_timestamp': format_timestamp(timestamp),
                            'guest_name': current_speaker,
                            'guest_last_line': current_line_text,
                            'transition_line': line.strip(),
                            'confidence': 'medium',
                            'requires_verification': True
                        }

                    # Track current speaker and line
                    current_speaker = speaker
                    current_line_start = timestamp
                    current_line_text = line.strip()

        return None

    except Exception as e:
        return {'status': 'error', 'message': f'Transcript parsing error: {str(e)}'}


def extract_waveform_data(params):
    """
    Extract amplitude waveform data from audio file.

    Returns frame-by-frame RMS levels so you can SEE where amplitude changes.

    Args:
        params: Dictionary with:
            - guest_key: Episode guest key
            - start_time: Start in seconds (default 1500 = 25min)
            - duration: Duration in seconds (default 900 = 15min)

    Returns:
        List of {time, rms_db, frame} showing amplitude at each second
    """
    guest_key = params.get('guest_key')
    if not guest_key:
        return {'status': 'error', 'message': 'Missing guest_key'}

    audio_file = params.get('audio_file', f'audio/{guest_key}.mp3')
    if not os.path.exists(audio_file):
        return {'status': 'error', 'message': f'Audio file not found: {audio_file}'}

    start_time = params.get('start_time', 1500)  # 25 min
    duration = params.get('duration', 900)  # 15 min

    try:
        # Extract RMS levels frame-by-frame
        result = subprocess.run([
            'ffmpeg', '-i', audio_file,
            '-ss', str(start_time),
            '-t', str(duration),
            '-af', 'astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-',
            '-f', 'null', '-'
        ], capture_output=True, text=True, timeout=120)

        # Parse RMS data (comes from stdout when using ametadata=print)
        frames = []
        frame_count = 0
        for line in result.stdout.split('\n'):
            if 'lavfi.astats.Overall.RMS_level=' in line:
                rms_str = line.split('=')[1].strip()
                rms_db = float(rms_str) if rms_str != '-inf' else -999
                timestamp = start_time + frame_count
                frames.append({
                    'frame': frame_count,
                    'time_seconds': timestamp,
                    'time_formatted': format_timestamp(timestamp),
                    'rms_db': rms_db
                })
                frame_count += 1

        # Find amplitude spikes (10+ dB increase)
        spikes = []
        for i in range(1, len(frames)):
            if frames[i]['rms_db'] > -900 and frames[i-1]['rms_db'] > -900:
                jump = frames[i]['rms_db'] - frames[i-1]['rms_db']
                if jump > 10:  # 10+ dB increase
                    spikes.append({
                        'time': frames[i]['time_formatted'],
                        'time_seconds': frames[i]['time_seconds'],
                        'jump_db': jump,
                        'from_db': frames[i-1]['rms_db'],
                        'to_db': frames[i]['rms_db']
                    })

        return {
            'status': 'success',
            'guest_key': guest_key,
            'frames': frames,
            'spikes': spikes,
            'message': f'Extracted {len(frames)} frames, found {len(spikes)} amplitude spikes'
        }

    except Exception as e:
        return {'status': 'error', 'message': f'FFmpeg error: {str(e)}'}


def prepare_midroll_analysis_data(params):
    """
    Extracts waveform and transcript data for Claude to analyze.

    No smart detection - just raw data extraction. Claude reads the waveform
    visualization and transcript to determine the correct midroll timestamp.

    Args:
        params: Dictionary with:
            - guest_key: Episode guest key
            - start_time: Start in seconds (default 1500 = 25 min)
            - duration: Duration in seconds (default 900 = 15 min)

    Returns:
        Dictionary with waveform data and transcript segment
    """
    guest_key = params.get('guest_key')
    if not guest_key:
        return {'status': 'error', 'message': 'Missing guest_key'}

    start_time = params.get('start_time', 1500)  # 25 min
    duration = params.get('duration', 900)  # 15 min

    # Resolve audio file
    audio_file = f'audio/{guest_key}.mp3'
    if not os.path.exists(audio_file):
        return {'status': 'error', 'message': f'Audio file not found: {audio_file}'}

    # Resolve transcript file
    transcript_file = resolve_transcript_file(guest_key)
    if not transcript_file or not os.path.exists(transcript_file):
        return {'status': 'error', 'message': f'Transcript file not found for guest: {guest_key}'}

    # STEP 1: Extract waveform RMS levels
    try:
        result = subprocess.run([
            'ffmpeg', '-i', audio_file,
            '-ss', str(start_time),
            '-t', str(duration),
            '-af', 'astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-',
            '-f', 'null', '-'
        ], capture_output=True, text=True, timeout=120)

        waveform = []
        frame_count = 0
        for line in result.stdout.split('\n'):
            if 'lavfi.astats.Overall.RMS_level=' in line:
                rms_str = line.split('=')[1].strip()
                rms_db = float(rms_str) if rms_str != '-inf' else -999
                timestamp_sec = start_time + frame_count

                # Format as MM:SS for readability
                mins = int(timestamp_sec // 60)
                secs = int(timestamp_sec % 60)

                waveform.append({
                    'time': f"{mins:02d}:{secs:02d}",
                    'seconds': timestamp_sec,
                    'rms_db': round(rms_db, 1)
                })
                frame_count += 1

    except Exception as e:
        return {'status': 'error', 'message': f'Waveform extraction failed: {str(e)}'}

    # STEP 2: Extract transcript segment
    try:
        with open(transcript_file, 'r', encoding='utf-8') as f:
            transcript_lines = []
            for line in f:
                # Check if line has timestamp in range
                ts_match = re.search(r'\[(\d{2}):(\d{2}):(\d{2})\]', line)
                if ts_match:
                    h, m, s = map(int, ts_match.groups())
                    timestamp = h * 3600 + m * 60 + s

                    if start_time <= timestamp <= start_time + duration:
                        transcript_lines.append(line.strip())

    except Exception as e:
        return {'status': 'error', 'message': f'Transcript extraction failed: {str(e)}'}

    return {
        'status': 'success',
        'guest_key': guest_key,
        'time_range': f"{start_time//60}:{start_time%60:02d} - {(start_time+duration)//60}:{(start_time+duration)%60:02d}",
        'waveform_frames': len(waveform),
        'waveform_sample': waveform[::100],  # Every 100th frame for quick viz
        'waveform_full': waveform,  # Full data if needed
        'transcript': '\n'.join(transcript_lines),
        'transcript_line_count': len(transcript_lines)
    }


def detect_midroll_timestamp(params):
    """
    Automatically detect midroll insertion timestamp using waveform analysis.

    Replicates manual Acast slider movement by:
    1. Finding amplitude dips in waveform (guest stops talking) 25-40 min range
    2. Finding amplitude recovery (host starts talking)
    3. Cross-referencing transcript to verify guest→host transition
    4. Returning timestamp where host starts (midroll insertion point)

    Args:
        params: Dictionary with:
            - guest_key: Episode guest key
            - audio_file: (optional) Path to audio file
            - transcript_file: (optional) Path to transcript file

    Returns:
        Dictionary with:
            - status: 'success' or 'error'
            - candidates: List of candidate timestamps with context
            - recommended: Top candidate
    """
    guest_key = params.get('guest_key')
    if not guest_key:
        return {'status': 'error', 'message': 'Missing guest_key'}

    # Resolve audio file
    audio_file = params.get('audio_file')
    if not audio_file:
        audio_file = f'audio/{guest_key}.mp3'

    if not os.path.exists(audio_file):
        return {'status': 'error', 'message': f'Audio file not found: {audio_file}'}

    # Resolve transcript file
    transcript_file = params.get('transcript_file')
    if not transcript_file:
        transcript_file = resolve_transcript_file(guest_key)

    if not transcript_file or not os.path.exists(transcript_file):
        return {'status': 'error', 'message': f'Transcript file not found for guest: {guest_key}'}

    # STEP 1: Extract waveform data (25-40 min range)
    try:
        result = subprocess.run([
            'ffmpeg', '-i', audio_file,
            '-ss', '1500',  # 25 min
            '-t', '900',    # 15 min duration
            '-af', 'astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-',
            '-f', 'null', '-'
        ], capture_output=True, text=True, timeout=120)

        # Parse RMS levels
        frames = []
        frame_count = 0
        for line in result.stdout.split('\n'):
            if 'lavfi.astats.Overall.RMS_level=' in line:
                rms_str = line.split('=')[1].strip()
                rms_db = float(rms_str) if rms_str != '-inf' else -999
                timestamp = 1500 + frame_count
                frames.append({
                    'time': timestamp,
                    'rms_db': rms_db
                })
                frame_count += 1

    except Exception as e:
        return {'status': 'error', 'message': f'Waveform extraction failed: {str(e)}'}

    # STEP 2: Find amplitude dips (guest stops) and recoveries (host starts)
    candidates = []
    dip_threshold = -28  # Below this = silence
    recovery_threshold = -25  # Above this = speaking

    in_dip = False
    dip_start = None

    for i in range(len(frames)):
        rms = frames[i]['rms_db']

        if rms > -900:  # Valid frame
            # Detect dip start (speaker stops)
            if not in_dip and rms < dip_threshold:
                in_dip = True
                dip_start = frames[i]['time']

            # Detect recovery (speaker starts)
            elif in_dip and rms > recovery_threshold:
                dip_end = frames[i]['time']
                dip_duration = dip_end - dip_start

                # Only consider dips lasting 1-10 seconds (natural pauses)
                if 1 <= dip_duration <= 10:
                    # Cross-reference with transcript
                    transition = find_speaker_transition(
                        transcript_file,
                        search_start=dip_start - 30,  # Look 30s before dip
                        search_end=dip_end + 30,      # Look 30s after recovery
                        host_name='Srini Rao'
                    )

                    if transition and transition.get('host_start_time'):
                        candidates.append({
                            'timestamp': format_timestamp(transition['host_start_time']),
                            'timestamp_seconds': transition['host_start_time'],
                            'guest_name': transition.get('guest_name', 'Unknown'),
                            'confidence': 'high' if dip_duration >= 2 else 'medium',
                            'waveform_dip': f"{dip_start}s → {dip_end}s ({dip_duration:.1f}s pause)",
                            'transcript_context': f"Guest: '{transition.get('guest_last_line', '')[:100]}...' → Host starts at {transition['host_start_timestamp']}"
                        })

                in_dip = False
                dip_start = None

    if not candidates:
        return {
            'status': 'error',
            'message': 'No clear guest→host transitions found in 25-40 minute range',
            'suggestion': 'Try adjusting time range or check transcript speaker labels'
        }

    # Sort by confidence and return top candidate
    candidates.sort(key=lambda x: (x['confidence'] == 'high', x['timestamp_seconds']))

    return {
        'status': 'success',
        'candidates': candidates[:5],  # Top 5
        'recommended': candidates[0],
        'guest_key': guest_key
    }


def normalize_speaker_name(speaker):
    """Normalize speaker name variations to canonical form

    Handles common variations:
    - Srini / Srinivas Rao / Srini Rao / Srini rao -> Srini Rao
    - Guest names with inconsistent casing

    Args:
        speaker (str): Raw speaker name from transcript

    Returns:
        str: Normalized speaker name
    """
    if not speaker:
        return speaker

    # Normalize whitespace and strip
    speaker = ' '.join(speaker.split()).strip()

    # Handle Srini variations
    speaker_lower = speaker.lower()
    if speaker_lower in ['srini', 'srinivas rao', 'srini rao', 'srinivas']:
        return 'Srini Rao'

    # Capitalize first letter of each word for consistency
    # But preserve all-caps acronyms
    words = speaker.split()
    normalized_words = []
    for word in words:
        if word.isupper() and len(word) > 1:
            # Keep acronyms as-is
            normalized_words.append(word)
        else:
            # Title case for regular words
            normalized_words.append(word.capitalize())

    return ' '.join(normalized_words)


def check_speaker_consistency(lines):
    """Check for multiple unique speakers in transcript

    Args:
        lines (list): Lines from formatted transcript

    Returns:
        dict: {
            'unique_speakers': set of unique speaker names,
            'speaker_count': int,
            'warning': str or None
        }
    """
    speakers = set()

    for line in lines:
        speaker_match = re.search(r'\*\*([^:*]+):\*\*', line)
        if speaker_match:
            speaker = normalize_speaker_name(speaker_match.group(1).strip())
            speakers.add(speaker)

    warning = None
    if len(speakers) > 2:
        warning = f"Warning: Found {len(speakers)} unique speakers: {sorted(speakers)}. Expected 2 (host + guest)."

    return {
        'unique_speakers': sorted(speakers),
        'speaker_count': len(speakers),
        'warning': warning
    }


def load_prep_guidelines():
    """Load podcast prep guidelines from JSON file"""
    try:
        with open(PODCAST_PREP_GUIDELINES, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        return {
            "error": f"Could not load prep guidelines: {str(e)}",
            "fallback_message": "Prep guidelines file missing or corrupted. Proceeding with default workflow."
        }


def resolve_transcript_file(guest_key):
    """Resolve guest key to actual transcript source_file using transcript_index.json"""
    if not os.path.exists(TRANSCRIPT_INDEX):
        return None
    
    try:
        with open(TRANSCRIPT_INDEX, 'r') as f:
            index_data = json.load(f)
        
        normalized_key = guest_key.lower().replace('-', '').replace('_', '').replace(' ', '')
        
        for entry_key, entry_data in index_data.get('entries', {}).items():
            normalized_entry_key = entry_key.lower().replace('-', '').replace('_', '').replace(' ', '')
            if normalized_key == normalized_entry_key:
                return entry_data.get('source_file')
            
            guest_name = entry_data.get('guest', '')
            normalized_guest = guest_name.lower().replace('-', '').replace('_', '').replace(' ', '')
            if normalized_key == normalized_guest:
                return entry_data.get('source_file')
        
        return None
    except Exception:
        return None


def update_transcript_status(guest_key, new_status):
    """Updates the status of a transcript in transcript_index.json"""
    if not os.path.exists(TRANSCRIPT_INDEX):
        return False
    
    try:
        with open(TRANSCRIPT_INDEX, 'r') as f:
            index = json.load(f)
        
        normalized_key = slugify(guest_key)
        updated = False
        
        for entry_key in index.get('entries', {}):
            if slugify(entry_key) == normalized_key:
                index['entries'][entry_key]['status'] = new_status
                updated = True
                break
        
        if updated:
            with open(TRANSCRIPT_INDEX, 'w') as f:
                json.dump(index, f, indent=2)
        
        return updated
    except:
        return False


def create_skeleton_entry(guest_key, force=False):
    """Creates a skeleton entry in podcast_index.json when transcript is processed
    
    Args:
        guest_key (str): Guest identifier
        force (bool): If True, overwrites existing entry even if it has content
    
    Returns:
        dict: {'created': bool, 'skipped_reason': str or None}
    """
    path = resolve_index()
    
    try:
        with open(path, 'r') as f:
            data = json.load(f)
    except:
        data = {'entries': {}}
    
    key = slugify(guest_key)
    
    # Check if entry already exists
    if key in data.get('entries', {}):
        existing = data['entries'][key]
        
        # If force is True, overwrite regardless
        if not force:
            # Check if entry has real content (not just skeleton)
            has_title = existing.get('title', '').strip() != ''
            has_summary = existing.get('summary', '').strip() != ''
            has_real_markers = existing.get('markers', ['']) != ['']
            is_published = existing.get('status') not in ['TBD', '']
            
            # Skip if entry has any real content
            if has_title or has_summary or has_real_markers or is_published:
                return {
                    'created': False,
                    'skipped_reason': 'Entry already exists with content'
                }
    
    # Create or overwrite skeleton entry
    data['entries'][key] = {
        'title': '',
        'summary': '',
        'alias': key,
        'status': 'TBD',
        'scheduled_publish_date': 'TBD',
        'audio': f'{key}.mp3',
        'markers': ['']
    }
    
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
    
    return {'created': True, 'skipped_reason': None}


def prep_transcript(params):
    """Parses raw transcript file, segments it into timestamped chunks by speaker"""
    guest_key = params.get('guest_key')
    if not guest_key:
        return {'status': 'error', 'message': 'Missing guest_key'}

    source_file = resolve_transcript_file(guest_key)
    if not source_file or not os.path.exists(source_file):
        return {'status': 'error', 'message': f"Transcript file not found for guest: {guest_key}"}

    speaker = ''
    os.makedirs('midrolls', exist_ok=True)
    formatted_path = f"midrolls/{os.path.basename(source_file).replace('.md', '.formatted.md')}"

    # First pass: normalize speaker names and write formatted output
    with open(source_file, 'r') as infile, open(formatted_path, 'w') as outfile:
        for line in infile:
            if '[' in line and re.search('\*\*[^:*]+:\*\*', line):
                name_match = re.search('\*\*([^:*]+):\*\*', line)
                if name_match:
                    raw_speaker = name_match.group(1).strip()
                    normalized_speaker = normalize_speaker_name(raw_speaker)

                    if normalized_speaker != speaker:
                        speaker = normalized_speaker
                        outfile.write(f'\n### {speaker}\n')

                    # Replace speaker name in line with normalized version
                    line = line.replace(f'**{raw_speaker}:**', f'**{normalized_speaker}:**')

            outfile.write(line)

    # Second pass: check speaker consistency
    with open(formatted_path, 'r') as f:
        lines = f.readlines()

    speaker_check = check_speaker_consistency(lines)

    resolved_key = slugify(os.path.basename(source_file).replace('.md', ''))

    result = {
        'status': 'success',
        'formatted_md': formatted_path,
        'resolved_key': resolved_key,
        'unique_speakers': speaker_check['unique_speakers'],
        'speaker_count': speaker_check['speaker_count']
    }

    if speaker_check['warning']:
        result['warning'] = speaker_check['warning']

    return result


def extract_midroll(params=None):
    """Extracts a midroll segment from a transcript based on static time window"""
    guest_key = params.get('guest_key') if params else None
    if not guest_key:
        return {'status': 'error', 'message': 'Missing guest_key'}
    
    source_file = resolve_transcript_file(guest_key)
    if not source_file or not os.path.exists(source_file):
        formatted_filename = source_file.replace('.md', '.formatted.md') if source_file else None
        if formatted_filename and os.path.exists(formatted_filename):
            source_file = formatted_filename
        else:
            return {'status': 'error', 'message': f"Transcript file not found for guest: {guest_key}"}
    
    start = '[00:25:00]'
    end = '[00:33:00]'
    capturing = False
    lines = []
    
    try:
        with open(source_file, 'r') as f:
            for line in f:
                if start in line:
                    capturing = True
                if capturing:
                    lines.append(line.rstrip())
                if end in line and capturing:
                    break
        
        os.makedirs('midrolls', exist_ok=True)
        resolved_key = slugify(os.path.basename(source_file).replace('.md', '').replace('.formatted', ''))
        output_path = f'midrolls/{resolved_key}.midroll.md'
        with open(output_path, 'w') as out:
            for l in lines:
                out.write(l + '\n')
        
        return {'status': 'success', 'output_file': output_path, 'resolved_key': resolved_key}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


def resolve_index():
    if not os.path.exists(PODCAST_INDEX):
        os.makedirs(os.path.dirname(PODCAST_INDEX), exist_ok=True)
        with open(PODCAST_INDEX, 'w') as f:
            json.dump({'entries': {}}, f)
    return PODCAST_INDEX


def add_episode_entry(params):
    """Add episode entry with flat parameters and auto-update transcript status"""
    key = slugify(params['entry_key'])
    title = params['title']
    summary = params['summary']
    midroll_time = params['midroll_time']
    scheduled_publish_date = params.get('scheduled_publish_date', 'TBD')
    
    try:
        minutes, seconds = map(int, midroll_time.strip().split(':'))
        total_seconds = round(minutes * 60 + seconds, 1)
        marker = f'midroll,{total_seconds}'
    except:
        return {'status': 'error', 'message': 'midroll_time must be mm:ss'}
    
    if scheduled_publish_date and scheduled_publish_date != 'TBD':
        status = 'scheduled'
    else:
        status = 'TBD'
    
    path = resolve_index()
    with open(path, 'r') as f:
        data = json.load(f)
    
    data['entries'][key] = {
        'title': title, 
        'summary': summary, 
        'alias': key,
        'status': status,
        'scheduled_publish_date': scheduled_publish_date, 
        'audio': key + '.mp3', 
        'markers': [marker]
    }
    
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
    
    update_transcript_status(key, 'processed')
    
    return {'status': 'success', 'message': f"Entry '{key}' added with status '{status}' and transcript marked processed."}


def update_episode_entry(params):
    """Update episode entry with flat parameters and ensure transcript is marked processed"""
    key = slugify(params.get('entry_key'))
    if not key:
        return {'status': 'error', 'message': 'Missing entry_key'}

    path = resolve_index()
    with open(path, 'r') as f:
        data = json.load(f)

    if key not in data.get('entries', {}):
        return {'status': 'error', 'message': f"Entry '{key}' not found"}

    # Store old entry for change detection
    old_entry = data['entries'][key].copy()

    update_fields = {k: v for k, v in params.items() if k != 'entry_key'}

    if not update_fields:
        return {'status': 'error', 'message': 'No update fields provided'}

    if 'midroll_time' in update_fields:
        try:
            minutes, seconds = map(int, update_fields['midroll_time'].strip().split(':'))
            total_seconds = round(minutes * 60 + seconds, 1)
            update_fields['markers'] = [f'midroll,{total_seconds}']
            del update_fields['midroll_time']
        except:
            return {'status': 'error', 'message': 'midroll_time must be mm:ss format'}

    if 'scheduled_publish_date' in update_fields:
        date = update_fields['scheduled_publish_date']
        if date and date != 'TBD':
            update_fields['status'] = 'scheduled'
        elif date == 'TBD':
            update_fields['status'] = 'TBD'

    data['entries'][key].update(update_fields)

    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

    update_transcript_status(key, 'processed')

    # Auto-sync to Acast if episode was previously uploaded
    sync_result = None
    episode_id = data['entries'][key].get('acast_episode_id')
    if episode_id:
        try:
            # Import here to avoid circular dependency
            from podcast_publisher import update_episode_on_acast

            # Detect which fields actually changed
            changed_fields = {}
            for field_key, field_value in update_fields.items():
                old_value = old_entry.get(field_key)
                if old_value != field_value:
                    changed_fields[field_key] = field_value

            if changed_fields:
                sync_success = update_episode_on_acast(key, episode_id, changed_fields)
                sync_result = 'synced' if sync_success else 'sync_failed'
            else:
                sync_result = 'no_changes'
        except ImportError:
            sync_result = 'sync_unavailable'
        except Exception as e:
            sync_result = f'sync_error: {str(e)}'

    result = {
        'status': 'success',
        'message': f"Entry '{key}' updated with {len(update_fields)} fields.",
        'updated_fields': list(update_fields.keys())
    }

    if sync_result:
        result['acast_sync'] = sync_result

    return result


def delete_episode_entry(params):
    key = slugify(params.get('entry_key'))
    path = resolve_index()
    with open(path, 'r') as f:
        data = json.load(f)
    if key in data.get('entries', {}):
        del data['entries'][key]
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
        return {'status': 'success', 'message': f"Entry '{key}' deleted."}
    return {'status': 'error', 'message': f"Entry '{key}' not found."}


def list_episode_entries(params):
    """List all episodes with minimal metadata, pagination, and sorting
    
    Params:
    - sort_by: field to sort by (default: 'title')
    - sort_order: 'asc' or 'desc' (default: 'asc')
    - page: page number (default: 1)
    - page_size: results per page (default: 20, max: 100)
    - fields: fields to return (default: ['title', 'status'])
    
    Returns: Same paginated structure as search_episode_entries
    """
    import math
    
    sort_by = params.get('sort_by', 'title')
    sort_order = params.get('sort_order', 'asc')
    page = params.get('page', 1)
    page_size = min(params.get('page_size', 20), 100)
    fields = params.get('fields', ['title', 'status'])
    
    path = 'data/podcast_index.json'
    if not os.path.exists(path):
        return {'status': 'error', 'message': 'Podcast index not found.'}
    
    try:
        with open(path, 'r') as f:
            data = json.load(f)
        
        entries = data.get('entries', {})
        
        # Convert to list for sorting
        results_list = [(k, v) for k, v in entries.items()]
        
        # Apply sorting
        reverse = (sort_order == 'desc')
        results_list.sort(key=lambda x: str(x[1].get(sort_by, '')), reverse=reverse)
        
        # Calculate pagination
        total_results = len(results_list)
        total_pages = math.ceil(total_results / page_size) if page_size > 0 else 0
        start = (page - 1) * page_size
        end = start + page_size
        
        # Slice for current page
        paginated_results = results_list[start:end]
        
        # Apply field selection
        formatted_results = []
        for entry_key, entry_value in paginated_results:
            filtered_entry = {'entry_key': entry_key}
            for field in fields:
                if field in entry_value:
                    filtered_entry[field] = entry_value[field]
            formatted_results.append(filtered_entry)
        
        return {
            'status': 'success',
            'results': formatted_results,
            'count': len(formatted_results),
            'page': page,
            'page_size': page_size,
            'total_pages': total_pages,
            'total_results': total_results
        }
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


def get_episode_entry(params):
    """Get a specific episode entry by key"""
    key = slugify(params.get('entry_key'))
    if not key:
        return {'status': 'error', 'message': 'Missing entry_key'}
    
    path = resolve_index()
    with open(path, 'r') as f:
        data = json.load(f)
    
    entry = data.get('entries', {}).get(key)
    if entry is None:
        return {'status': 'error', 'message': f"Entry '{key}' not found"}
    
    return {'status': 'success', 'entry': entry}


def search_episode_entries(params):
    """Search episode entries with pagination, sorting, and field selection
    
    Params:
    - search_value: string to search across all fields (optional)
    - filters: dict for exact key-value matching (optional)
    - sort_by: field name to sort by (default: 'title')
    - sort_order: 'asc' or 'desc' (default: 'asc')
    - page: page number, 1-indexed (default: 1)
    - page_size: results per page (default: 20, max: 100)
    - fields: list of field names to return (default: ['title', 'status', 'scheduled_publish_date'])
    
    Returns:
    {
      "status": "success",
      "results": [{"entry_key": "eric-barker", "title": "...", "status": "TBD"}, ...],
      "count": 15,
      "page": 1,
      "page_size": 20,
      "total_pages": 1,
      "total_results": 15
    }
    """
    import math
    
    search_value = params.get('search_value', '').lower()
    filters = params.get('filters', {})
    sort_by = params.get('sort_by', 'title')
    sort_order = params.get('sort_order', 'asc')
    page = params.get('page', 1)
    page_size = min(params.get('page_size', 20), 100)
    fields = params.get('fields', ['title', 'status', 'scheduled_publish_date'])

    if not search_value and not filters:
        return {'status': 'error', 'message': 'Must provide either search_value or filters'}

    path = resolve_index()
    with open(path, 'r') as f:
        data = json.load(f)

    entries = data.get('entries', {})
    results = {}

    # Apply filtering
    for entry_key, entry_value in entries.items():
        # Apply filters first (exact matching)
        if filters:
            matches_filters = True
            for filter_key, filter_value in filters.items():
                entry_field = entry_value.get(filter_key)
                if entry_field != filter_value:
                    matches_filters = False
                    break
            if not matches_filters:
                continue

        # Then apply search_value (fuzzy matching across all fields)
        if search_value:
            entry_blob = json.dumps(entry_value).lower()
            if search_value not in entry_blob:
                continue

        results[entry_key] = entry_value

    # Convert to list for sorting
    results_list = [(k, v) for k, v in results.items()]
    
    # Apply sorting
    reverse = (sort_order == 'desc')
    results_list.sort(key=lambda x: str(x[1].get(sort_by, '')), reverse=reverse)
    
    # Calculate pagination
    total_results = len(results_list)
    total_pages = math.ceil(total_results / page_size) if page_size > 0 else 0
    start = (page - 1) * page_size
    end = start + page_size
    
    # Slice for current page
    paginated_results = results_list[start:end]
    
    # Apply field selection
    formatted_results = []
    for entry_key, entry_value in paginated_results:
        filtered_entry = {'entry_key': entry_key}
        for field in fields:
            if field in entry_value:
                filtered_entry[field] = entry_value[field]
        formatted_results.append(filtered_entry)
    
    return {
        'status': 'success',
        'results': formatted_results,
        'count': len(formatted_results),
        'page': page,
        'page_size': page_size,
        'total_pages': total_pages,
        'total_results': total_results
    }


def audit_transcript_for_ads(params):
    """Preps a transcript and segments it for ad review based on timestamp blocks"""
    guest_key = params.get('guest_key')
    if not guest_key:
        return {'status': 'error', 'message': 'Missing guest_key'}
    
    source_file = resolve_transcript_file(guest_key)
    if not source_file or not os.path.exists(source_file):
        return {'status': 'error', 'message': f"Transcript file not found for guest: {guest_key}"}
    
    speaker = ''
    formatted_path = source_file.replace('.md', '.formatted.md')
    with open(source_file, 'r') as infile, open(formatted_path, 'w') as outfile:
        for line in infile:
            if '[' in line and re.search('\\*\\*[^:*]+:\\*\\*', line):
                name_match = re.search('\\*\\*([^:*]+):\\*\\*', line)
                if name_match:
                    new_speaker = name_match.group(1).strip()
                    if new_speaker != speaker:
                        speaker = new_speaker
                        outfile.write(f'\n### {speaker}\n')
            outfile.write(line)
    
    with open(formatted_path, 'r') as f:
        lines = f.readlines()
    
    chunks = []
    current_chunk = []
    chunk_start = CHUNK_START_SECONDS
    chunk_end = chunk_start + CHUNK_MINUTES * 60
    
    for line in lines:
        match = re.search(MIDROLL_TIMESTAMP_PATTERN, line)
        if not match:
            continue
        ts = match.group(0)
        seconds = parse_timestamp(ts)
        if seconds is None:
            continue
        if seconds > chunk_end:
            if current_chunk:
                chunks.append({'start': chunk_start, 'end': chunk_end, 'content': current_chunk})
            current_chunk = []
            chunk_start = chunk_end
            chunk_end += CHUNK_MINUTES * 60
        speaker_match = re.search('\\*\\*([^:*]+):\\*\\*', line)
        speaker = speaker_match.group(1).strip() if speaker_match else 'Unknown'
        text = line[line.find(']') + 1:].strip()
        current_chunk.append({'timestamp': ts, 'speaker': speaker, 'text': text})
    
    if current_chunk:
        chunks.append({'start': chunk_start, 'end': chunk_end, 'content': current_chunk})
    
    resolved_key = slugify(os.path.basename(source_file).replace('.md', ''))
    chunk_paths = []
    for i, chunk in enumerate(chunks):
        out_path = f'transcript_audit/{resolved_key}.part_{i + 1}.json'
        os.makedirs('transcript_audit', exist_ok=True)
        with open(out_path, 'w') as f:
            json.dump(chunk, f, indent=2)
        chunk_paths.append(out_path)
    
    index_path = f'transcript_audit/{resolved_key}.index.json'
    with open(index_path, 'w') as f:
        json.dump(chunk_paths, f, indent=2)
    
    return {'status': 'success', 'index_file': index_path, 'formatted_md': formatted_path, 'resolved_key': resolved_key}


def read_midroll_file(params):
    """Reads a previously extracted midroll segment file and returns raw markdown content"""
    entry_key = params.get('entry_key')
    if not entry_key:
        return {'status': 'error', 'message': 'Missing entry_key'}
    
    path = f'midrolls/{slugify(entry_key)}.midroll.md'
    if not os.path.exists(path):
        return {'status': 'error', 'message': f'Midroll file not found: {path}'}
    
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    return {'status': 'success', 'content': content}


def read_index_file(params):
    """Reads a podcast transcript index file and returns list of chunked file paths"""
    if params.get('entry_key'):
        filename = params.get('entry_key')
    elif params.get('filename') and params.get('filename') != 'auto_generated.json':
        filename = params.get('filename')
    else:
        filename = None
    
    if not filename:
        return {'status': 'error', 'message': 'Missing filename or entry_key'}

    slugified_name = slugify(filename)

    possible_paths = [
        filename,
        f"transcript_chunks/{filename}",
        f"transcript_chunks/{filename}.index.json",
        f"transcript_chunks/{slugified_name}",
        f"transcript_chunks/{slugified_name}.index.json",
        f"data/{filename}",
        f"data/{filename}.index.json"
    ]

    path = next((p for p in possible_paths if os.path.exists(p)), None)
    if not path:
        return {'status': 'error', 'message': 'Index file not found.'}

    with open(path, 'r', encoding='utf-8') as f:
        content = json.load(f)

    return {'status': 'success', 'files': content}


def read_transcript_chunk(params):
    """Reads a specific transcript chunk JSON file and returns structured content by timestamp"""
    chunk_id = params.get('chunk_id')
    if not chunk_id:
        return {'status': 'error', 'message': 'Missing chunk_id'}

    path = f'transcript_chunks/{chunk_id}.json'
    if not os.path.exists(path):
        return {'status': 'error', 'message': f'Chunk file not found: {path}'}

    with open(path, 'r', encoding='utf-8') as f:
        content = json.load(f)
    return {'status': 'success', 'content': content}


def process_episode_transcript(params):
    """
    Self-contained workflow: runs prep_transcript, extracts midroll analysis data,
    creates skeleton entry, loads guidelines.

    Returns status and saves midroll analysis data for Claude review.
    """
    guest_key = params.get("guest_key")
    if not guest_key:
        return {"status": "error", "message": "Missing guest_key"}

    # Step 1: Prep transcript
    prep_result = prep_transcript({"guest_key": guest_key})
    if prep_result.get("status") != "success":
        return {"status": "error", "message": "prep_transcript failed", "details": prep_result}

    resolved_key = prep_result.get('resolved_key', slugify(guest_key))

    # Step 2: Extract midroll analysis data (waveform + transcript)
    midroll_data_result = prepare_midroll_analysis_data({
        "guest_key": resolved_key,
        "start_time": 1500,  # 25 min
        "duration": 900      # 15 min
    })

    midroll_analysis_saved = False
    if midroll_data_result.get("status") == "success":
        # Save analysis data to file for Claude review
        os.makedirs('data/midroll_analysis', exist_ok=True)
        analysis_file = f'data/midroll_analysis/{resolved_key}.json'

        with open(analysis_file, 'w') as f:
            json.dump(midroll_data_result, f, indent=2)

        midroll_analysis_saved = True

    # Step 3: Create skeleton entry
    skeleton_result = create_skeleton_entry(resolved_key)

    # Step 4: Load guidelines
    guidelines = load_prep_guidelines()

    return {
        "status": "success",
        "message": "Episode transcript processed. Midroll analysis data extracted for Claude review.",
        "guest_key": resolved_key,
        "formatted_md": prep_result.get("formatted_md"),
        "midroll_analysis_file": f'data/midroll_analysis/{resolved_key}.json' if midroll_analysis_saved else None,
        "skeleton_created": skeleton_result.get('created'),
        "skeleton_skipped_reason": skeleton_result.get('skipped_reason'),
        "prep_workflow": guidelines.get("entries", {}).get("prep_workflow", {}),
        "title_summary_rules": guidelines.get("entries", {}).get("title_summary_rules", {})
    }


def create_transcript_batch(params):
    """Creates a batch file containing a list of guest keys to process together"""
    batch_name = params.get('batch_name')
    guest_keys = params.get('guest_keys', [])
    
    if not batch_name:
        return {'status': 'error', 'message': 'Missing batch_name'}
    if not guest_keys or not isinstance(guest_keys, list):
        return {'status': 'error', 'message': 'Missing or invalid guest_keys list'}
    
    valid_keys = []
    invalid_keys = []
    
    for guest_key in guest_keys:
        if resolve_transcript_file(guest_key):
            valid_keys.append(guest_key)
        else:
            invalid_keys.append(guest_key)
    
    if invalid_keys:
        return {
            'status': 'error', 
            'message': f'Transcript files not found for: {invalid_keys}',
            'valid_keys': valid_keys
        }
    
    os.makedirs('batches', exist_ok=True)
    batch_file = f'batches/{slugify(batch_name)}.batch.json'
    
    batch_data = {
        'batch_name': batch_name,
        'created': datetime.now().isoformat(),
        'guest_keys': valid_keys,
        'total_count': len(valid_keys)
    }
    
    with open(batch_file, 'w') as f:
        json.dump(batch_data, f, indent=2)
    
    return {
        'status': 'success', 
        'batch_file': batch_file,
        'valid_count': len(valid_keys),
        'message': f'Batch created with {len(valid_keys)} valid guest keys'
    }


def create_batch_from_unprocessed(params):
    """Creates a batch automatically from all unprocessed transcripts in transcript_index.json"""
    if not os.path.exists(TRANSCRIPT_INDEX):
        return {'status': 'error', 'message': 'Transcript index not found'}
    
    try:
        with open(TRANSCRIPT_INDEX, 'r') as f:
            index = json.load(f)
    except Exception as e:
        return {'status': 'error', 'message': f'Failed to read transcript index: {str(e)}'}
    
    unprocessed = []
    for entry_key, entry_data in index.get('entries', {}).items():
        if entry_data.get('status') == 'unprocessed':
            unprocessed.append(entry_key)
    
    if not unprocessed:
        return {
            'status': 'success', 
            'message': 'No unprocessed transcripts found. All transcripts have been processed!',
            'unprocessed_count': 0
        }
    
    batch_name = params.get('batch_name', f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    
    return create_transcript_batch({
        'batch_name': batch_name,
        'guest_keys': unprocessed
    })


def process_transcript_batch(params):
    """Processes all transcripts in a batch file using process_episode_transcript"""
    batch_name = params.get('batch_name')
    if not batch_name:
        return {'status': 'error', 'message': 'Missing batch_name'}
    
    batch_file = f'batches/{slugify(batch_name)}.batch.json'
    if not os.path.exists(batch_file):
        return {'status': 'error', 'message': f'Batch file not found: {batch_file}'}
    
    try:
        with open(batch_file, 'r') as f:
            batch_data = json.load(f)
    except Exception as e:
        return {'status': 'error', 'message': f'Failed to read batch file: {str(e)}'}
    
    guest_keys = batch_data.get('guest_keys', [])
    if not guest_keys:
        return {'status': 'error', 'message': 'No guest keys found in batch file'}
    
    results = {
        'batch_name': batch_name,
        'total_count': len(guest_keys),
        'successful': [],
        'failed': [],
        'skipped': [],
        'details': {}
    }
    
    for i, guest_key in enumerate(guest_keys, 1):
        # No print statements - just process silently
        result = process_episode_transcript({'guest_key': guest_key})
        
        if result.get('status') == 'success':
            results['successful'].append(guest_key)
            results['details'][guest_key] = {
                'status': 'success',
                'resolved_key': result.get('guest_key'),
                'formatted_md': result.get('formatted_md'),
                'index_file': result.get('index_file'),
                'midroll_file': result.get('midroll_file'),
                'skeleton_created': result.get('skeleton_created'),
                'skeleton_skipped_reason': result.get('skeleton_skipped_reason')
            }
            
            # Track skipped entries separately
            if not result.get('skeleton_created'):
                results['skipped'].append(guest_key)
        else:
            results['failed'].append(guest_key)
            results['details'][guest_key] = {
                'status': 'failed',
                'error': result.get('message', 'Unknown error'),
                'details': result.get('details', {})
            }
    
    results['success_count'] = len(results['successful'])
    results['failure_count'] = len(results['failed'])
    results['skipped_count'] = len(results['skipped'])

    results_file = f'batches/{slugify(batch_name)}.results.json'
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)

    # Build Claude prompt message
    claude_prompt = f"""
✅ Batch processing complete: {results['success_count']} successful, {results['failure_count']} failed, {results['skipped_count']} skipped

📊 Midroll analysis data extracted to: data/midroll_analysis/

🤖 NEXT: Read data/midroll_detection_prompt.json for Claude analysis instructions
"""

    return {
        'status': 'success',
        'batch_results': results,
        'results_file': results_file,
        'message': f'Batch processing complete: {results["success_count"]} successful, {results["failure_count"]} failed, {results["skipped_count"]} skipped (already had content)',
        'claude_next_step': claude_prompt.strip()
    }

def main():
    import argparse, json
    parser = argparse.ArgumentParser()
    parser.add_argument('action')
    parser.add_argument('--params')
    args = parser.parse_args()
    params = json.loads(args.params) if args.params else {}

    if args.action == 'prep_transcript':
        result = prep_transcript(params)
    elif args.action == 'extract_midroll':
        result = extract_midroll(params)
    elif args.action == 'process_episode_transcript':
        result = process_episode_transcript(params)
    elif args.action == 'create_transcript_batch':
        result = create_transcript_batch(params)
    elif args.action == 'create_batch_from_unprocessed':
        result = create_batch_from_unprocessed(params)
    elif args.action == 'process_transcript_batch':
        result = process_transcript_batch(params)
    elif args.action == 'add_episode_entry':
        result = add_episode_entry(params)
    elif args.action == 'update_episode_entry':
        result = update_episode_entry(params)
    elif args.action == 'delete_episode_entry':
        result = delete_episode_entry(params)
    elif args.action == 'get_episode_entry':
        result = get_episode_entry(params)
    elif args.action == 'search_episode_entries':
        result = search_episode_entries(params)
    elif args.action == 'list_episode_entries':
        result = list_episode_entries(params)
    elif args.action == 'audit_transcript_for_ads':
        result = audit_transcript_for_ads(params)
    elif args.action == 'read_midroll_file':
        result = read_midroll_file(params)
    elif args.action == 'detect_midroll_timestamp':
        result = detect_midroll_timestamp(params)
    elif args.action == 'extract_waveform_data':
        result = extract_waveform_data(params)
    elif args.action == 'prepare_midroll_analysis_data':
        result = prepare_midroll_analysis_data(params)
    else:
        result = {'status': 'error', 'message': f'Unknown action {args.action}'}

    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()