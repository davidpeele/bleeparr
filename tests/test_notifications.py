import smtplib
from unittest.mock import Mock
import pytest
from test_app import client, job
from backend import store, notifications as n


@pytest.fixture
def configured(client):
    store.save_settings(dict(email_enabled=True,smtp_host='mail.example',smtp_from='sender@example.com',smtp_to='user@example.com'))
    return store.settings()


def finish(config, result=None):
    store.enqueue(job())
    claimed=store.claim(3)
    store.finish(claimed,result or {'success':True,'mute_count':2},config)
    return claimed


def test_success_outbox_is_durable_and_not_duplicated(configured):
    claimed=finish(configured)
    store.finish(claimed,{'success':True},configured)
    assert len(n.history()) == 1
    assert n.history()[0]['status'] == 'pending'
    store.init()
    assert len(n.history()) == 1


def test_disabled_and_event_preferences(client,configured):
    finish({**configured,'email_enabled':False})
    assert not n.history()
    client.post('/api/jobs/1/retry')  # completed job cannot be retried
    with store.db() as db:
        db.execute("UPDATE jobs SET status='queued',next_try=0")
    finish({**configured,'notify_completed':False})
    assert not n.history()


def test_retry_alerts_are_opt_in_and_final_failures_notify(configured):
    claimed=finish(configured,{'success':False,'error_code':'subtitle_missing','error':'secret-should-not-send'})
    assert not n.history()
    with store.db() as db:
        db.execute("UPDATE jobs SET status='queued',next_try=0,attempts=2")
    claimed=store.claim(3)
    store.finish(claimed,{'success':False,'error_code':'subtitle_missing','error':'secret-should-not-send'},configured)
    assert n.history()[0]['event'] == 'failed'
    with store.db() as db:
        assert 'secret-should-not-send' not in db.execute('SELECT body FROM notifications').fetchone()[0]


def test_retry_notification_when_selected(configured):
    finish({**configured,'notify_retry':True},{'success':False,'error_code':'busy'})
    assert n.history()[0]['event'] == 'retry'


def test_smtp_starttls_and_snapshot_addresses(configured,monkeypatch):
    finish(configured)
    smtp=Mock();smtp.send_message.return_value={}
    constructor=Mock(return_value=smtp);monkeypatch.setattr(n.smtplib,'SMTP',constructor)
    store.save_settings({'smtp_to':'changed@example.com','smtp_username':'login','smtp_password':'secret'})
    assert n.deliver_one()
    assert n.history()[0]['status'] == 'sent'
    smtp.starttls.assert_called_once()
    smtp.login.assert_called_once_with('login','secret')
    msg=smtp.send_message.call_args.args[0]
    assert msg['To'] == 'user@example.com'
    assert 'secret' not in msg.as_string()


def test_implicit_tls(configured,monkeypatch):
    finish(configured)
    store.save_settings({'smtp_security':'ssl','smtp_port':465})
    smtp=Mock();smtp.send_message.return_value={}
    constructor=Mock(return_value=smtp);monkeypatch.setattr(n.smtplib,'SMTP_SSL',constructor)
    n.deliver_one()
    constructor.assert_called_once()
    smtp.starttls.assert_not_called()


def test_connect_failure_retries_without_affecting_media(configured,monkeypatch):
    finish(configured)
    monkeypatch.setattr(n.smtplib,'SMTP',Mock(side_effect=OSError('secret credential text')))
    n.deliver_one()
    item=n.history()[0]
    assert item['status'] == 'pending' and item['attempts'] == 1
    assert 'secret' not in item['error']
    assert store.jobs()[0]['status'] == 'completed'
    assert not n.deliver_one()  # retry delay applies
    with store.db() as db:
        db.execute('UPDATE notifications SET next_try=0,attempts=4')
    n.deliver_one()
    assert n.history()[0]['status'] == 'failed'


def test_ambiguous_delivery_does_not_auto_resend(configured,monkeypatch):
    finish(configured)
    smtp=Mock();smtp.send_message.side_effect=TimeoutError('private text')
    monkeypatch.setattr(n.smtplib,'SMTP',Mock(return_value=smtp))
    n.deliver_one()
    assert n.history()[0]['status'] == 'unknown'
    assert not n.deliver_one()
    n.retry(n.history()[0]['id'])
    assert n.history()[0]['status'] == 'pending'


def test_shutdown_during_sending_recovers_as_uncertain(configured):
    finish(configured)
    n.claim()
    store.init()
    assert n.history()[0]['status'] == 'unknown'


def test_email_disabled_pauses_pending(configured):
    finish(configured)
    store.save_settings({'email_enabled':False})
    assert not n.deliver_one()
    assert n.history()[0]['attempts'] == 0


def test_settings_validation_redaction_and_test_queue(client):
    assert client.put('/api/settings',json={'email_enabled':True}).status_code == 400
    assert client.put('/api/settings',json={'smtp_to':'a@example.com\nBcc:bad@example.com'}).status_code == 400
    assert client.put('/api/settings',json={'smtp_security':'none','smtp_username':'login'}).status_code == 400
    assert client.put('/api/settings',json={'smtp_password':'secret'}).status_code == 200
    result=client.get('/api/settings').json()
    assert result['smtp_password'] == '' and result['smtp_password_configured']
    client.put('/api/settings',json={'smtp_password':''})
    assert store.settings()['smtp_password'] == 'secret'


def test_test_button_queues_only_and_rate_limits(client,configured,monkeypatch):
    sender=Mock();monkeypatch.setattr(n.smtplib,'SMTP',sender)
    assert client.post('/api/notifications/test').status_code == 200
    assert client.post('/api/notifications/test').status_code == 400
    sender.assert_not_called()
    assert client.get('/api/notifications').json()['items'][0]['event'] == 'test'


def test_no_matches_email_uses_completion_preference_without_clean_claim(configured):
    finish(configured,{'success':True,'outcome':'no_matches_found'})
    with store.db() as db:
        row=db.execute('SELECT subject,body FROM notifications').fetchone()
    assert 'No matching words found' in row['subject']
    assert 'No cleaned file was created' in row['body']
    assert 'free of profanity' in row['body']
