"""Final compressed-image byte gate; no network/model calls."""
import pytest
from pipeline.agent_shadow import read, write
from pipeline.agent_shadow_details import images


@pytest.mark.parametrize('size,accepted', [(19999, False), (20000, True), (20001, True)])
@pytest.mark.parametrize('cached', [False, True])
def test_final_webp_byte_floor_including_resume(tmp_path, size, accepted, cached):
    relative = 'article_images/news-x.webp'
    asset = tmp_path / 'reader' / relative
    final = {'News': [{'winner': {'id': 'x', 'og_image': 'https://example.invalid/photo'}}]}
    def fetch(url, dest):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b'x' * size)
        return {'original_bytes': 59051}
    if cached:
        fetch('', asset)
        write(tmp_path / 'image-results.json', {'x': {'ok': True, 'seconds': 0}})
    images(tmp_path, final, lambda *a: None, False, fetcher=fetch)
    report = read(tmp_path / 'image-results.json')['x']
    assert report['ok'] is accepted
    assert report['final_bytes'] == size
    assert bool(final['News'][0]['_image_local']) is accepted
    assert asset.exists() is accepted
    if not accepted:
        assert report['reason'] == 'compressed image below 20000 bytes'
        assert (tmp_path / 'rejected-images' / 'news-x.webp').stat().st_size == size
