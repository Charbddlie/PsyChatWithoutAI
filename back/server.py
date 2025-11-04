import csv
import hashlib
import json
import math
import random
import re
import string
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import logging

HOST = '0.0.0.0'
PORT = 8765
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / 'data'
USER_RECORD_PATH = DATA_DIR / 'user_record.tsv'
GROUP_SEQUENCE_PATH = DATA_DIR / 'group_sequence.json'

RETURN_INCOMPLETE_SWITCH_GROUP = True  # 是否允许相同用户尝试另一个group的题目

REQUIRED_FORM_FILES = [
  'pre1-info.json',
  'pre2.json',
  'pre3.json',
  'post1.json',
  'post2.json',
  'post3.json',
  'post4.json',
  'post5.json',
  'post6_1.json',
  'post6_2.json',
]

GROUP_KEYS = ('group1', 'group2', 'group3', 'group4')

DATA_DIR.mkdir(exist_ok=True)

USER_RECORD_BASE_COLUMNS = [
  'userid',
  'group',
  'lesson-duration_seconds',
  'pre1-age',
  'pre1-gender',
  'pre1-major',
  'pre1-grade',
  'pre1-ai_attitude',
  'pre2-positive_affect',
  'pre2-negative_affect',
  'pre3-average_score',
  'pre4-total_score',
  'post1-sociability',
  'post1-animacy',
  'post1-agency',
  'post1-teaching_support',
  'post1-disturbance',
  'post2-1',
  'post2-2',
  'post3-positive_affect',
  'post3-negative_affect',
  'post4-ability_trust',
  'post4-benevolence_trust',
  'post4-integrity_trust',
  'post4-overall_trust',
  'post5-average_score',
  'post6_1-total_score',
  'post6_2-q1-answer',
  'post6_2-q1-score',
  'post6_2-q2-answer',
  'post6_2-q2-score',
  'post6_2-q3-answer',
  'post6_2-q3-score',
  'post6_2-q4-answer',
  'post6_2-q4-score',
]

FORM_QUESTION_INDICES = (
  ('pre1-info', range(1, 6)),
  ('pre2', range(1, 9)),
  ('pre3', range(1, 10)),
  ('pre4', range(1, 16)),
  ('post1', range(1, 26)),
  ('post2', range(1, 3)),
  ('post3', range(1, 9)),
  ('post4', range(1, 12)),
  ('post5', range(1, 6)),
  ('post6_1', range(1, 16)),
  ('post6_2', range(1, 5)),
)

FORM_SELECTED_CHOICE_COLUMNS = []
for form_key, indices in FORM_QUESTION_INDICES:
  for index in indices:
    column = f'{form_key}-q{index}-answer'
    if column not in USER_RECORD_BASE_COLUMNS and column not in FORM_SELECTED_CHOICE_COLUMNS:
      FORM_SELECTED_CHOICE_COLUMNS.append(column)

USER_RECORD_COLUMNS = USER_RECORD_BASE_COLUMNS + FORM_SELECTED_CHOICE_COLUMNS

LOG_DIR = BASE_DIR / 'log'
LOG_DIR.mkdir(exist_ok=True)
log_filename = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S.log')
log_path = LOG_DIR / log_filename

logger = logging.getLogger("psychat")
logger.setLevel(logging.INFO)

file_handler = logging.FileHandler(log_path, encoding='utf-8')
file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))

console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))

logger.addHandler(file_handler)
logger.addHandler(console_handler)

def stringify_value(value):
  if value is None:
    return ''
  if isinstance(value, list):
    parts = []
    for item in value:
      part = stringify_value(item)
      if part:
        parts.append(part)
    return '; '.join(parts)
  if isinstance(value, float):
    if math.isnan(value) or math.isinf(value):
      return ''
    formatted = f'{value:.6f}'.rstrip('0').rstrip('.')
    return formatted or '0'
  if isinstance(value, int):
    return str(value)
  return str(value)


def sanitize_tsv_value(value):
  text = stringify_value(value)
  if not text:
    return ''
  text = text.replace('\t', '    ')
  text = text.replace('\r', ' ')
  text = text.replace('\n', ' ')
  sanitized = []
  for char in text:
    if char == ' ':
      sanitized.append(char)
    elif char.isprintable():
      sanitized.append(char)
    else:
      sanitized.append(' ')
  return ''.join(sanitized).strip()


def read_json_file(path):
  if not path.exists():
    return None
  try:
    return json.loads(path.read_text(encoding='utf-8'))
  except (json.JSONDecodeError, OSError):
    return None


def extract_answer(form_record, target_index):
  answers = form_record.get('payload', {}).get('answers', []) if isinstance(form_record, dict) else []
  for fallback_index, entry in enumerate(answers, start=1):
    if not isinstance(entry, dict):
      continue
    index = entry.get('index') or fallback_index
    if index == target_index:
      return entry.get('selected_choice')
  return None


def record_form_answers(row, form_key, form_record):
  if not isinstance(row, dict) or not form_key or not isinstance(form_record, dict):
    return
  answers = form_record.get('payload', {}).get('answers', [])
  if not isinstance(answers, list):
    return
  for fallback_index, entry in enumerate(answers, start=1):
    if not isinstance(entry, dict):
      continue
    index = entry.get('index') or fallback_index
    column = f'{form_key}-q{index}-answer'
    if column in row:
      row[column] = sanitize_tsv_value(entry.get('selected_choice'))


def build_user_record_row(user_id):
  user_dir = DATA_DIR / user_id
  if not user_dir.exists():
    return None

  forms_dir = user_dir / 'forms'
  forms_dir_exists = forms_dir.exists()
  row = {column: '' for column in USER_RECORD_COLUMNS}
  row['userid'] = sanitize_tsv_value(user_id)

  group_data = read_json_file(user_dir / 'group.json') or {}
  row['group'] = sanitize_tsv_value(group_data.get('group'))

  lesson_record = read_json_file(user_dir / 'lesson.json')
  if lesson_record:
    duration_ms = lesson_record.get('payload', {}).get('duration_ms') if isinstance(lesson_record, dict) else None
    if isinstance(duration_ms, (int, float)):
      row['lesson-duration_seconds'] = sanitize_tsv_value(duration_ms / 1000)
    elif duration_ms is not None:
      row['lesson-duration_seconds'] = sanitize_tsv_value(duration_ms)

  pre1 = read_json_file(forms_dir / 'pre1-info.json') if forms_dir_exists else None
  if pre1:
    record_form_answers(row, 'pre1-info', pre1)
    row['pre1-age'] = sanitize_tsv_value(extract_answer(pre1, 1))
    row['pre1-gender'] = sanitize_tsv_value(extract_answer(pre1, 2))
    row['pre1-major'] = sanitize_tsv_value(extract_answer(pre1, 3))
    row['pre1-grade'] = sanitize_tsv_value(extract_answer(pre1, 4))
    row['pre1-ai_attitude'] = sanitize_tsv_value(extract_answer(pre1, 5))

  pre2 = read_json_file(forms_dir / 'pre2.json') if forms_dir_exists else None
  if pre2:
    record_form_answers(row, 'pre2', pre2)
  if pre2 and isinstance(pre2.get('score'), dict):
    row['pre2-positive_affect'] = sanitize_tsv_value(pre2['score'].get('positive_affect'))
    row['pre2-negative_affect'] = sanitize_tsv_value(pre2['score'].get('negative_affect'))

  pre3 = read_json_file(forms_dir / 'pre3.json') if forms_dir_exists else None
  if pre3:
    record_form_answers(row, 'pre3', pre3)
  if pre3 and isinstance(pre3.get('score'), dict):
    row['pre3-average_score'] = sanitize_tsv_value(pre3['score'].get('average_score'))

  pre4 = read_json_file(forms_dir / 'pre4.json') if forms_dir_exists else None
  if pre4:
    record_form_answers(row, 'pre4', pre4)
  if pre4 and isinstance(pre4.get('score'), dict):
    row['pre4-total_score'] = sanitize_tsv_value(pre4['score'].get('total_score'))

  post1 = read_json_file(forms_dir / 'post1.json') if forms_dir_exists else None
  if post1:
    record_form_answers(row, 'post1', post1)
  if post1 and isinstance(post1.get('score'), dict):
    for key in ('sociability', 'animacy', 'agency', 'teaching_support', 'disturbance'):
      column = f'post1-{key}'
      if column in row:
        row[column] = sanitize_tsv_value(post1['score'].get(key))

  post2 = read_json_file(forms_dir / 'post2.json') if forms_dir_exists else None
  if post2:
    record_form_answers(row, 'post2', post2)
    scores = post2.get('score', {}).get('scores', {}) if isinstance(post2.get('score'), dict) else {}
    for key in ('1', '2'):
      column = f'post2-{key}'
      if column in row:
        row[column] = sanitize_tsv_value(scores.get(key))

  post3 = read_json_file(forms_dir / 'post3.json') if forms_dir_exists else None
  if post3:
    record_form_answers(row, 'post3', post3)
  if post3 and isinstance(post3.get('score'), dict):
    row['post3-positive_affect'] = sanitize_tsv_value(post3['score'].get('positive_affect'))
    row['post3-negative_affect'] = sanitize_tsv_value(post3['score'].get('negative_affect'))

  post4 = read_json_file(forms_dir / 'post4.json') if forms_dir_exists else None
  if post4:
    record_form_answers(row, 'post4', post4)
  if post4 and isinstance(post4.get('score'), dict):
    for key in ('ability_trust', 'benevolence_trust', 'integrity_trust', 'overall_trust'):
      column = f'post4-{key}'
      if column in row:
        row[column] = sanitize_tsv_value(post4['score'].get(key))

  post5 = read_json_file(forms_dir / 'post5.json') if forms_dir_exists else None
  if post5:
    record_form_answers(row, 'post5', post5)
  if post5 and isinstance(post5.get('score'), dict):
    row['post5-average_score'] = sanitize_tsv_value(post5['score'].get('average_score'))

  post6_1 = read_json_file(forms_dir / 'post6_1.json') if forms_dir_exists else None
  if post6_1:
    record_form_answers(row, 'post6_1', post6_1)
  if post6_1 and isinstance(post6_1.get('score'), dict):
    row['post6_1-total_score'] = sanitize_tsv_value(post6_1['score'].get('total_score'))

  post6_2 = read_json_file(forms_dir / 'post6_2.json') if forms_dir_exists else None
  if post6_2:
    record_form_answers(row, 'post6_2', post6_2)

  return row


def upsert_user_record(row):
  if not row or 'userid' not in row or not row['userid']:
    return

  existing_rows = []
  header_matches = False
  if USER_RECORD_PATH.exists():
    try:
      with USER_RECORD_PATH.open('r', encoding='utf-8', newline='') as handle:
        reader = csv.reader(handle, delimiter='\t')
        header = next(reader, None)
        header_matches = header == USER_RECORD_COLUMNS
        if header_matches:
          for current in reader:
            if not current:
              continue
            userid = current[0]
            existing_rows.append((userid, current))
    except OSError:
      existing_rows = []
      header_matches = False

  if not header_matches:
    existing_rows = []

  row_values = [row.get(column, '') for column in USER_RECORD_COLUMNS]
  updated = False
  for idx, (userid, _) in enumerate(existing_rows):
    if userid == row['userid']:
      existing_rows[idx] = (userid, row_values)
      updated = True
      break
  if not updated:
    existing_rows.append((row['userid'], row_values))

  with USER_RECORD_PATH.open('w', encoding='utf-8', newline='') as handle:
    writer = csv.writer(handle, delimiter='\t', lineterminator='\n')
    writer.writerow(USER_RECORD_COLUMNS)
    for _, values in existing_rows:
      writer.writerow(values)


def read_existing_user_record_userids():
  if not USER_RECORD_PATH.exists():
    return set()
  try:
    with USER_RECORD_PATH.open('r', encoding='utf-8', newline='') as handle:
      reader = csv.reader(handle, delimiter='\t')
      header = next(reader, None)
      if header != USER_RECORD_COLUMNS:
        return set()
      userids = set()
      for row in reader:
        if not row:
          continue
        user_id = row[0]
        if user_id:
          userids.add(user_id)
      return userids
  except OSError:
    return set()


def has_complete_user_data(user_id):
  user_dir = DATA_DIR / user_id
  if not user_dir.exists():
    return False
  if not (user_dir / 'group.json').exists():
    return False
  forms_dir = user_dir / 'forms'
  if not forms_dir.exists():
    return False
  for filename in REQUIRED_FORM_FILES:
    if not (forms_dir / filename).exists():
      return False
  return True


def bootstrap_user_records():
  rows = []
  for entry in sorted(DATA_DIR.iterdir(), key=lambda path: path.name):
    if not entry.is_dir():
      continue
    user_id = entry.name
    row = build_user_record_row(user_id)
    if row:
      rows.append(row)

  try:
    with USER_RECORD_PATH.open('w', encoding='utf-8', newline='') as handle:
      writer = csv.writer(handle, delimiter='\t', lineterminator='\n')
      writer.writerow(USER_RECORD_COLUMNS)
      for row in rows:
        writer.writerow([row.get(column, '') for column in USER_RECORD_COLUMNS])
  except OSError:
    return


bootstrap_user_records()


def generate_user_id(length=16):
  charset = string.ascii_lowercase + string.digits
  return ''.join(random.choices(charset, k=length))


def ensure_user_directories(user_id):
  user_dir = DATA_DIR / user_id
  forms_dir = user_dir / 'forms'
  user_dir.mkdir(parents=True, exist_ok=True)
  forms_dir.mkdir(parents=True, exist_ok=True)
  return user_dir, forms_dir


def load_user_meta(user_dir):
  meta_file = user_dir / 'meta.json'
  if not meta_file.exists():
    return {}
  try:
    return json.loads(meta_file.read_text(encoding='utf-8'))
  except json.JSONDecodeError:
    return {}


def save_user_meta(user_dir, meta):
  meta_file = user_dir / 'meta.json'
  meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
  return meta_file


def load_group_sequence_index():
  if not GROUP_SEQUENCE_PATH.exists():
    return 0
  try:
    data = json.loads(GROUP_SEQUENCE_PATH.read_text(encoding='utf-8'))
  except (json.JSONDecodeError, OSError):
    return 0
  index = data.get('next_index', 0)
  if isinstance(index, int):
    return index % len(GROUP_KEYS)
  try:
    parsed = int(index)
  except (TypeError, ValueError):
    return 0
  return parsed % len(GROUP_KEYS)


def save_group_sequence_index(index):
  payload = {'next_index': index % len(GROUP_KEYS)}
  try:
    GROUP_SEQUENCE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
  except OSError:
    pass


def assign_group(user_id, user_dir):
  group_file = user_dir / 'group.json'
  if not RETURN_INCOMPLETE_SWITCH_GROUP and group_file.exists():
    try:
      data = json.loads(group_file.read_text(encoding='utf-8'))
      group = data.get('group')
      if group in GROUP_KEYS:
        return group
    except json.JSONDecodeError:
      pass

  index = load_group_sequence_index()
  group = GROUP_KEYS[index]
  payload = {
    'group': group,
    'assigned_at': datetime.now(timezone.utc).isoformat(),
  }
  group_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
  save_group_sequence_index(index + 1)
  return group


def parse_numeric(value):
  if isinstance(value, (int, float)):
    return float(value)
  if isinstance(value, str):
    stripped = value.strip()
    if not stripped:
      return None
    try:
      return float(stripped)
    except ValueError:
      return None
  return None


def answers_to_map(answers):
  mapping = {}
  if not isinstance(answers, list):
    return mapping
  for idx, entry in enumerate(answers, start=1):
    if not isinstance(entry, dict):
      continue
    key = entry.get('index') or idx
    mapping[int(key)] = entry.get('selected_choice')
  return mapping


def collect_numeric_values(answers, indices):
  mapping = answers_to_map(answers)
  values = []
  for index in indices:
    numeric = parse_numeric(mapping.get(index))
    if numeric is not None:
      values.append(numeric)
  return values


def mean(values):
  return sum(values) / len(values) if values else None


def score_pre2(answers):
  positive = collect_numeric_values(answers, range(1, 6))
  negative = collect_numeric_values(answers, range(6, 11))
  return {
    'positive_affect': mean(positive),
    'negative_affect': mean(negative),
  }


def score_pre3(answers):
  values = [parse_numeric(value) for value in answers_to_map(answers).values()]
  numeric_values = [value for value in values if value is not None]
  return {
    'average_score': mean(numeric_values),
  }

def score_pre4(answers):
  values = [parse_numeric(value) for value in answers_to_map(answers).values()]
  numeric_values = [value for value in values if value is not None]
  return {
    'total_score': sum(numeric_values),
  }


POST1_DIMENSIONS = {
  'sociability': range(1, 6),
  'animacy': range(6, 11),
  'agency': range(11, 16),
  'teaching_support': range(16, 22),
  'disturbance': range(22, 26),
}


def score_post1(answers):
  results = {}
  for dimension, indices in POST1_DIMENSIONS.items():
    values = collect_numeric_values(answers, indices)
    results[dimension] = mean(values)
  return results


def score_post3(answers):
  positive = collect_numeric_values(answers, range(1, 6))
  negative = collect_numeric_values(answers, range(6, 11))
  return {
    'positive_affect': mean(positive),
    'negative_affect': mean(negative),
  }


def score_post4(answers):
  ability = collect_numeric_values(answers, range(1, 6))
  benevolence = collect_numeric_values(answers, range(6, 9))
  integrity = collect_numeric_values(answers, range(9, 12))
  ability_score = mean(ability)
  benevolence_score = mean(benevolence)
  integrity_score = mean(integrity)
  overall_components = [score for score in (ability_score, benevolence_score, integrity_score) if score is not None]
  overall = mean(overall_components)
  return {
    'ability_trust': ability_score,
    'benevolence_trust': benevolence_score,
    'integrity_trust': integrity_score,
    'overall_trust': overall,
  }


def score_average(answers):
  values = [parse_numeric(value) for value in answers_to_map(answers).values()]
  numeric_values = [value for value in values if value is not None]
  return {'average_score': mean(numeric_values)}


POST61_CORRECT = {
  1: {'A', 'B', 'C', 'D'},
  2: {'A', 'B'},
  3: {'A', 'B', 'C'},
  4: {'A', 'B', 'C'},
  5: {'A'},
  6: {'B'},
  7: {'C'},
  8: {'A', 'B', 'C'},
  9: {'A', 'B'},
  10: {'A'},
  11: {'D'},
  12: {'A', 'B', 'C'},
  13: {'B'},
  14: {'A', 'B', 'C'},
  15: {'C'},
}


def extract_letter(choice):
  if isinstance(choice, str):
    match = re.search(r'[A-Z]', choice.upper())
    if match:
      return match.group(0)
  return None


def score_post61(answers):
  score = 0
  details = []
  for index, expected in POST61_CORRECT.items():
    entry = next((item for item in answers if isinstance(item, dict) and (item.get('index') or 0) == index), None)
    selections = entry.get('selected_choice') if isinstance(entry, dict) else None
    if not isinstance(selections, list):
      selections = selections or []
      selections = [selections]
    letters = set()
    for choice in selections:
      letter = extract_letter(choice)
      if letter:
        letters.add(letter)
    is_correct = letters == expected
    if is_correct:
      score += 1
    details.append({
      'index': index,
      'selected': sorted(letters),
      'expected': sorted(expected),
      'is_correct': is_correct,
    })
  return {
    'total_score': score,
    'max_score': len(POST61_CORRECT),
    'details': details,
  }

def score_form(form_key, payload):
  answers = payload.get('answers') if isinstance(payload, dict) else None
  if not answers:
    return None

  if form_key == 'pre2':
    return score_pre2(answers)
  if form_key == 'pre3':
    return score_pre3(answers)
  if form_key == 'pre4':
    return score_pre4(answers)
  if form_key == 'post1':
    return score_post1(answers)
  if form_key == 'post2':
    mapped = {}
    for index, value in answers_to_map(answers).items():
      numeric = parse_numeric(value)
      mapped[str(index)] = numeric if numeric is not None else value
    return {'scores': mapped}
  if form_key == 'post3':
    return score_post3(answers)
  if form_key == 'post4':
    return score_post4(answers)
  if form_key == 'post5':
    return score_average(answers)
  if form_key == 'post6_1':
    return score_post61(answers)
  if form_key == 'post6_2':
    return None  # post6_2 now stores raw answers without automated scoring
  return None


class RequestHandler(BaseHTTPRequestHandler):
  server_version = 'PsyChatBackend/1.0'

  def log_message(self, format, *args):  # noqa: A003 - BaseHTTPRequestHandler signature
    return

  def end_headers(self):
    self.send_header('Access-Control-Allow-Origin', '*')
    self.send_header('Access-Control-Allow-Headers', 'Content-Type')
    self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    super().end_headers()

  def do_OPTIONS(self):  # noqa: N802 - BaseHTTPRequestHandler naming
    self.send_response(204)
    self.end_headers()

  def do_POST(self):  # noqa: N802
    parsed = urlparse(self.path)
    if parsed.path == '/register':
      self.handle_register()
    elif parsed.path == '/submit-form':
      self.handle_submit_form()
    elif parsed.path == '/lesson-complete':
      self.handle_lesson_complete()
    elif parsed.path == '/completion':
      self.handle_completion_post()
    else:
      self.send_json(404, {'message': 'Not Found'})

  def do_GET(self):  # noqa: N802
    parsed = urlparse(self.path)
    if parsed.path == '/group':
      self.handle_group(parsed)
    elif parsed.path == '/completion':
      self.handle_completion_get(parsed)
    elif parsed.path == '/user-record':
      self.handle_user_record_download()
    else:
      self.send_json(404, {'message': 'Not Found'})

  def parse_json_body(self):
    content_length = int(self.headers.get('Content-Length', 0))
    if content_length == 0:
      return None
    raw_body = self.rfile.read(content_length)
    try:
      return json.loads(raw_body.decode('utf-8'))
    except json.JSONDecodeError:
      return None

  def handle_register(self):
    user_id = generate_user_id()
    user_dir, _ = ensure_user_directories(user_id)
    logger.info(f'New user registered: {user_id}')
    meta = load_user_meta(user_dir)
    meta['user_id'] = user_id
    meta['registered_at'] = datetime.now(timezone.utc).isoformat()
    meta.setdefault('completed', False)
    save_user_meta(user_dir, meta)
    self.send_json(200, {'userid': user_id})

  def handle_submit_form(self):
    payload = self.parse_json_body()
    if not isinstance(payload, dict):
      self.send_json(200, {'status': 'success'})
      return

    user_id = payload.get('userid')
    form_key = payload.get('form_key') or 'unknown'

    if not user_id:
      self.send_json(200, {'status': 'success'})
      return
    logger.info(f'User {user_id} submitted form {form_key}')
    _, forms_dir = ensure_user_directories(user_id)
    timestamp = datetime.now(timezone.utc).isoformat()
    score = score_form(form_key, payload) if form_key != 'pre1' else None
    record = {
      'received_at': timestamp,
      'payload': payload,
    }
    if score is not None:
      record['score'] = score
    file_path = forms_dir / f'{form_key}.json'
    file_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    self.send_json(200, {'status': 'success'})

  def handle_lesson_complete(self):
    payload = self.parse_json_body()
    if not isinstance(payload, dict):
      self.send_json(200, {'status': 'success'})
      return

    user_id = payload.get('userid') or ''
    if not user_id:
      self.send_json(200, {'status': 'success'})
      return
    
    logger.info(f'User {user_id} completed lesson')
    user_dir, _ = ensure_user_directories(user_id)
    timestamp = datetime.now(timezone.utc).isoformat()
    record = {
      'received_at': timestamp,
      'payload': payload,
    }
    file_path = user_dir / 'lesson.json'
    file_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    self.send_json(200, {'status': 'success'})

  def handle_completion_get(self, parsed):
    query = parse_qs(parsed.query)
    user_id = query.get('userid', [''])[0]
    if not user_id:
      self.send_json(400, {'message': 'userid 参数不能为空'})
      return

    user_dir, _ = ensure_user_directories(user_id)
    if RETURN_INCOMPLETE_SWITCH_GROUP:
      self.send_json(200, {'completed': False})
      logger.info(f'User {user_id} completion status requested: False (incomplete switch mode)')
      return
    
    meta = load_user_meta(user_dir)
    completed = bool(meta.get('completed', False))
    logger.info(f'User {user_id} completion status requested: {completed}')
    self.send_json(200, {'completed': completed})

  def handle_completion_post(self):
    payload = self.parse_json_body()
    if not isinstance(payload, dict):
      self.send_json(200, {'status': 'success'})
      return

    user_id = (payload.get('userid') or '').strip()
    if not user_id:
      self.send_json(400, {'message': 'userid 参数不能为空'})
      return

    logger.info(f'User {user_id} set completion status')
    user_dir, _ = ensure_user_directories(user_id)
    meta = load_user_meta(user_dir)
    meta.setdefault('user_id', user_id)
    completed_flag = bool(payload.get('completed', True))
    meta['completed'] = completed_flag
    timestamp = datetime.now(timezone.utc).isoformat()
    if completed_flag:
      meta['completed_at'] = timestamp
    else:
      meta.pop('completed_at', None)
    meta['status_updated_at'] = timestamp
    save_user_meta(user_dir, meta)
    if completed_flag:
      row = build_user_record_row(user_id)
      if row:
        upsert_user_record(row)
    self.send_json(200, {'status': 'success', 'completed': completed_flag})

  def handle_group(self, parsed):
    query = parse_qs(parsed.query)
    user_id = query.get('userid', [''])[0]
    if not user_id:
      self.send_json(400, {'message': 'userid 参数不能为空'})
      return

    user_dir, _ = ensure_user_directories(user_id)
    group = assign_group(user_id, user_dir)
    logger.info(f'User {user_id} assigned group: {group}')
    self.send_json(200, {'group': group})

  def handle_user_record_download(self):
    bootstrap_user_records()
    if not USER_RECORD_PATH.exists():
      self.send_json(404, {'message': '记录文件不存在'})
      return

    try:
      content = USER_RECORD_PATH.read_bytes()
    except OSError:
      self.send_json(500, {'message': '记录文件读取失败'})
      return

    self.send_response(200)
    self.send_header('Content-Type', 'text/tab-separated-values; charset=utf-8')
    self.send_header('Content-Length', str(len(content)))
    self.send_header('Content-Disposition', 'attachment; filename="user_record.tsv"')
    self.end_headers()
    self.wfile.write(content)

  def send_json(self, status_code, payload):
    body = json.dumps(payload, ensure_ascii=False)
    encoded = body.encode('utf-8')
    self.send_response(status_code)
    self.send_header('Content-Type', 'application/json; charset=utf-8')
    self.send_header('Content-Length', str(len(encoded)))
    self.end_headers()
    self.wfile.write(encoded)


def run():
  server = HTTPServer((HOST, PORT), RequestHandler)
  print(f'Backend server running at http://{HOST}:{PORT}')
  try:
    server.serve_forever(poll_interval=0.2)
  except KeyboardInterrupt:
    pass
  finally:
    server.server_close()
    print('Backend server stopped')


if __name__ == '__main__':
  run()
