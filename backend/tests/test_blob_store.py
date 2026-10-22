from unittest.mock import MagicMock, patch

from app.data import blob_store


def test_build_blob_name_is_owner_prefixed():
    name = blob_store.build_blob_name("user-1", "conv-9", "png")
    assert name.startswith("user-1/conv-9/")
    assert name.endswith(".png")


@patch("app.data.blob_store._service")
def test_generate_read_sas_url_refuses_unowned_path(mock_service):
    # A blob under another user's prefix must never get a SAS, and must not even touch the
    # storage service (fails closed before any delegation key is requested).
    url = blob_store.generate_read_sas_url("someone-else/conv/abc.jpg", "user-1")

    assert url is None
    mock_service.assert_not_called()


@patch("app.data.blob_store.generate_blob_sas", return_value="sig=redacted")
@patch("app.data.blob_store._service")
def test_generate_read_sas_url_mints_url_for_owned_blob(mock_service, mock_sas):
    service = MagicMock()
    service.account_name = "stacct"
    service.get_user_delegation_key.return_value = MagicMock()
    mock_service.return_value = service

    with patch.object(blob_store.settings, "blob_endpoint", "https://stacct.blob.core.windows.net/"):
        url = blob_store.generate_read_sas_url("user-1/conv/abc.jpg", "user-1")

    assert url == "https://stacct.blob.core.windows.net/uploads/user-1/conv/abc.jpg?sig=redacted"
    service.get_user_delegation_key.assert_called_once()
    # read-only permission on the SAS
    assert mock_sas.call_args.kwargs["permission"].read is True
