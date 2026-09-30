"""Durable email delivery independent of media processing; no raw worker logs in email."""
from email.message import EmailMessage
from email.utils import make_msgid
import smtplib
import ssl
import time
import uuid
from backend import store


def enqueue(db, job, result, status, config):
    if status == 'skipped':
        return
    preference = 'completed' if status == 'no_matches' else 'failed' if status == 'review' or (status=='blocked' and result.get('error_code')=='original_storage_full') else status
    if not config['email_enabled'] or not config.get('notify_' + preference, False):
        return
    title = ' '.join(job['title'].split())[:200]
    labels = {'completed': 'Completed', 'failed': 'Needs attention', 'retry': 'Retry scheduled', 'no_matches': 'No matching words found',
              'review':'Review required','blocked':'Waiting for storage or folder access'}
    subject = f"Bleeparr — {labels[status]}: {title}"
    body = [f'Title: {title}', f'Status: {labels[status]}', f"Processing attempt: {job['attempts']}"]
    if status == 'no_matches':
        body += ['No matching words were found in the selected subtitles. No cleaned file was created.', 'This does not prove the audio is free of profanity. Open Activity for subtitle details.']
    elif status == 'completed':
        body += [f"Muted intervals: {result.get('mute_count', 0)}", f"Subtitle fallback sections: {result.get('fallback_sections', 0)}"]
    else:
        code = result.get('error_code', 'unknown')
        # Codes are bounded; error messages/logs may contain credentials or private paths.
        body += [f"Reason: {str(code)[:80]}", 'Open Bleeparr Activity for details.']
        if status == 'retry':
            body.append('Another processing attempt will be made after the retry delay.')
        else:
            body.append('Processing stopped for this file. Review the failure before retrying.')
    insert(db, subject, '\n'.join(body), config, job['id'], status)


def insert(db, subject, body, config, job_id=None, event='test'):
    now = time.time()
    db.execute('''INSERT INTO notifications(id,job_id,event,subject,body,recipient,sender,message_id,status,attempts,next_try,created,updated)
        VALUES (?,?,?,?,?,?,?,?,?,0,?,?,?)''',
        (uuid.uuid4().hex, job_id, event, subject, body, config['smtp_to'], config['smtp_from'],
         make_msgid(domain='bleeparr.local'), 'pending', now, now, now))


def queue_test():
    config = store.settings()
    if not config['email_enabled']:
        raise ValueError('Enable and save email notifications first')
    with store.db() as db:
        db.execute('BEGIN IMMEDIATE')
        recent = db.execute("SELECT 1 FROM notifications WHERE event='test' AND created>?", (time.time() - 60,)).fetchone()
        if recent:
            raise ValueError('Please wait one minute before sending another test email')
        insert(db, 'Bleeparr — Test notification', 'Your Bleeparr email notifications are configured. This is a test message.', config)
    return {'message': 'Test email queued. Check delivery history for the result.'}


def history():
    with store.db() as db:
        return [dict(r) for r in db.execute('SELECT id,job_id,event,subject,recipient,status,attempts,error,created,updated FROM notifications ORDER BY created DESC LIMIT 30')]


def claim():
    with store.db() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute("SELECT * FROM notifications WHERE status='pending' AND next_try<=? ORDER BY created LIMIT 1", (time.time(),)).fetchone()
        if row:
            db.execute("UPDATE notifications SET status='sending',attempts=attempts+1,updated=? WHERE id=?", (time.time(), row['id']))
            return {**dict(row), 'attempts': row['attempts'] + 1}


def deliver(item, config):
    message = EmailMessage()
    message['Subject'] = item['subject']
    message['From'] = item['sender']
    message['To'] = item['recipient']
    message['Message-ID'] = item['message_id']
    message.set_content(item['body'])
    smtp = None
    sending = False
    try:
        if config['smtp_security'] == 'ssl':
            smtp = smtplib.SMTP_SSL(config['smtp_host'], config['smtp_port'], timeout=20, context=ssl.create_default_context())
        else:
            smtp = smtplib.SMTP(config['smtp_host'], config['smtp_port'], timeout=20)
            smtp.ehlo()
            if config['smtp_security'] == 'starttls':
                smtp.starttls(context=ssl.create_default_context())
                smtp.ehlo()
        if config['smtp_username']:
            smtp.login(config['smtp_username'], config['smtp_password'])
        sending = True
        refused = smtp.send_message(message)
        if refused:
            return 'failed', 'Recipient was rejected by the mail server'
        return 'sent', ''
    except (smtplib.SMTPRecipientsRefused, smtplib.SMTPSenderRefused, smtplib.SMTPAuthenticationError):
        return 'failed', 'Mail credentials, sender or recipient were rejected; check email settings'
    except smtplib.SMTPDataError:
        return 'pending', 'Mail server rejected the message; delivery will be retried'
    except Exception:
        if sending:
            return 'unknown', 'Connection ended during delivery; email may have been accepted. Review before manually retrying.'
        return 'pending', 'Could not connect securely to the mail server; check email settings'
    finally:
        if smtp is not None:
            try:
                smtp.close()
            except Exception:
                pass


def deliver_one():
    config = store.settings()
    if not config['email_enabled']:
        return False
    item = claim()
    if not item:
        return False
    status, error = deliver(item, config)
    if status == 'pending' and item['attempts'] >= 5:
        status = 'failed'
        error = 'Delivery stopped after five attempts; check email settings and retry manually'
    delay = min(3600, 60 * 2 ** (item['attempts'] - 1))
    with store.db() as db:
        db.execute('UPDATE notifications SET status=?,error=?,next_try=?,updated=? WHERE id=?',
                   (status,error,time.time()+delay,time.time(),item['id']))
    return True


def retry(notification_id):
    with store.db() as db:
        if not db.execute("UPDATE notifications SET status='pending',attempts=0,next_try=0,error='' WHERE id=? AND status IN ('failed','unknown')", (notification_id,)).rowcount:
            raise ValueError('Only failed or uncertain deliveries can be retried')
    return {'message': 'Email queued again. An uncertain previous delivery may already have reached your inbox.'}


def worker(stop):
    while not stop.is_set():
        try:
            if deliver_one():
                continue
        except Exception:
            # Do not log third-party exception text: SMTP messages may expose credentials.
            store.event('Notification worker encountered an error; check delivery history')
        stop.wait(2)
