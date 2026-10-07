from atbmind_core.storage.schemas import MessageRecord, SessionRecord

def test_storage_schemas_import_and_defaults():
    msg = MessageRecord(session_id="s1", role="user", content="hello")
    assert msg.session_id == "s1"
    assert msg.role == "user"
    assert msg.content == "hello"

    sess = SessionRecord(session_id="s1", title="Title")
    assert sess.session_id == "s1"
    assert sess.title == "Title"
