from .calibration import brier


def review(rows):
    return dict(mode='offline_fixture',mature_labels=len(rows),brier=brier(rows),approved=False,auto_apply=False,
                model_or_schema_changed=False,verdict='INCONCLUSIVO',note='Fixtures testam o software, não rentabilidade, latência ou calibração de um provedor.')
