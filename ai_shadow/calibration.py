from .contracts import numeric


def label(prediction,entry,exit,now):
    numeric(now,0)
    p=numeric(prediction['probability'],0,1);at=numeric(prediction['predicted_at'],0)
    if entry is None or exit is None:return None
    for quote in (entry,exit):
        numeric(quote['time'],0);numeric(quote['received_at'],0)
        if quote['time']>quote['received_at'] or quote['received_at']-quote['time']>5:return None
    if entry['time']<=at or entry['received_at']>now:return None
    target=entry['time']+3600
    if not target<=exit['time']<=target+5 or exit['received_at']>now:return None
    ask=numeric(entry['ask'],1e-300);bid=numeric(exit['bid'],1e-300)
    net_return=bid/ask*(.999*.999)/(1.001*1.001)-1
    numeric(net_return)
    return dict(probability=p,outcome=int(net_return>0),label_at=exit['received_at'],predicted_at=at,net_return=net_return,mode='offline_fixture')


def brier(rows):
    if not rows:return None
    values=[]
    for r in rows:
        p=numeric(r['probability'],0,1)
        if type(r['outcome']) is not int or r['outcome'] not in (0,1):raise ValueError('Label binário obrigatório')
        numeric(r['label_at'],0);numeric(r['predicted_at'],0)
        if r['label_at']<=r['predicted_at']:raise ValueError('Label não é futuro')
        values.append((p-r['outcome'])**2)
    return sum(values)/len(values)


def baseline(rows,cutoff):
    numeric(cutoff,0)
    for r in rows:numeric(r['label_at'],0)
    eligible=[r for r in rows if r['label_at']<=cutoff]
    if not eligible:return None
    if any(type(r['outcome']) is not int or r['outcome'] not in (0,1) for r in eligible):raise ValueError('Label inválido')
    return sum(r['outcome'] for r in eligible)/len(eligible)
