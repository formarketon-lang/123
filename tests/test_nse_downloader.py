
from data.providers.nse_downloader import (
    create_nse_session,
    download_equity_history,
    save_nse_csv,
)


def test_nse_downloader_imports():
    assert callable(create_nse_session)
    assert callable(download_equity_history)
    assert callable(save_nse_csv)
  
