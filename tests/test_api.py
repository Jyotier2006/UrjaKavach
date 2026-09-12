import io
import pytest
from PIL import Image


def test_health_and_no_fabricated_metrics(client):
    assert client.get('/health').json()['status'] == 'ok'
    metrics = client.get('/metrics/models').json()
    assert all(m['care'] is None for m in metrics['care']['models'])
    assert client.get('/scenarios/sim-gearbox-drift/scores?model=M1').status_code == 409


def test_bounded_telemetry_and_bad_queries(client):
    result = client.get('/scenarios/sim-gearbox-drift/telemetry?max_points=20').json()
    assert len(result['data']) == 20
    assert result['provenance'] == 'Simulated'
    assert client.get('/scenarios/missing/telemetry').status_code == 404
    assert client.get('/scenarios/sim-gearbox-drift/telemetry?signals=event_label').status_code == 422
    assert client.get('/scenarios/sim-gearbox-drift/telemetry?from=20&to=1').status_code == 422


def test_workorder_lifecycle_enforces_checklist(client):
    order = {'id': 'WO-TEST', 'asset_id': 'T-03', 'title': 'Inspection', 'checklist': [{'text': 'Record findings', 'done': False}]}
    assert client.post('/workorders', json=order).status_code == 201
    assert client.post('/workorders', json=order).status_code == 409
    assert client.patch('/workorders/WO-TEST', json={'status': 'Completed'}).status_code == 409
    assert client.patch('/workorders/WO-TEST', json={'status': 'In progress'}).status_code == 200
    assert client.patch('/workorders/WO-TEST', json={'status': 'Awaiting review'}).status_code == 422
    assert client.patch('/workorders/WO-TEST', json={'checklist': [{'text': 'Record findings', 'done': True}], 'notes': 'Checked.'}).status_code == 200
    assert client.patch('/workorders/WO-TEST', json={'status': 'Awaiting review'}).status_code == 200
    assert client.patch('/workorders/WO-TEST', json={'status': 'Completed'}).json()['status'] == 'Completed'
    assert any(o['id'] == 'WO-TEST' and o['notes'] == 'Checked.' for o in client.get('/workorders').json())


def test_api_optimizer_persists_and_validates(client):
    response = client.post('/schedule/optimize', json={'crew_count': 1})
    assert response.status_code == 200
    result = response.json()
    assert client.get('/schedules/' + result['id']).json()['items'] == result['items']
    assert client.post('/schedule/optimize', json={'crew_count': 0}).status_code == 422
    assert client.post('/loss/estimate', json={'delay_days': 30, 'horizon_days': 14}).status_code == 422
    assert client.post('/loss/estimate', json={'assumptions': {'capacity_factor': 2}}).status_code == 422


def _flat_module_png() -> bytes:
    output = io.BytesIO(); Image.new('L', (24, 40), 128).save(output, format='PNG')
    return output.getvalue()


def test_image_screening_without_weights_never_claims_classification(client, monkeypatch):
    """D007: with no classifier loaded the endpoint reports image quality only."""
    from services.api.app.domain import inspection
    monkeypatch.setattr(inspection, '_classifier', lambda: None)
    response = client.post('/solar/ir/classify', files={'file': ('module.png', _flat_module_png(), 'image/png')})
    assert response.status_code == 200
    result = response.json()
    assert result['confidence'] is None and result['probabilities'] is None
    assert result['stored'] is False
    assert result['label'] == 'Low image contrast'
    assert result['heatmap_kind'] == 'Pixel intensity map, not Grad-CAM'
    assert client.post('/solar/ir/classify', files={'file': ('bad.png', b'not an image', 'image/png')}).status_code == 422


def test_image_screening_with_weights_reports_class_and_grad_cam(client):
    """D016: with the committed weights present the endpoint classifies and explains."""
    from services.ml import ir_classifier
    if not ir_classifier.available():
        pytest.skip('trained weights not present')
    response = client.post('/solar/ir/classify', files={'file': ('module.png', _flat_module_png(), 'image/png')})
    assert response.status_code == 200
    result = response.json()
    assert result['label'] in ir_classifier.CLASSES
    assert 0 <= result['confidence'] <= 1
    assert abs(sum(result['probabilities'].values()) - 1) < 1e-2
    assert result['heatmap_kind'].startswith('Grad-CAM')
    assert 'CNN' in result['method'] and result['stored'] is False


def test_stream_warning_ack_and_deduplication(client):
    with client.websocket_connect('/ws/alerts') as ws:
        assert ws.receive_json()['type'] == 'connected'
        response = client.post('/ingest/replay', json={'scenario_id': 'sim-gearbox-drift', 'step': 185})
        assert response.status_code == 200
        alert = ws.receive_json()
        assert alert['type'] == 'alert' and alert['severity'] == 'Warning'
        count = len(client.get('/alerts').json())
        client.post('/ingest/replay', json={'scenario_id': 'sim-gearbox-drift', 'step': 185})
        assert len(client.get('/alerts').json()) == count
        assert client.post('/alerts/' + alert['id'] + '/ack').json()['state'] == 'Acknowledged'
        assert ws.receive_json()['type'] == 'acknowledged'

