"""Conservative personal evidence gates. No predicted or averaged blend scores."""
from datetime import datetime


def known(value):
    return value is not None and value not in ['', 'unknown', 'automatic']


def similar_context(current,previous):
    # A past unknown cannot establish similarity to a known current condition.
    for key in ['daypart','occasion','environment']:
        if known(current.get(key)) and current[key]!=previous.get(key):return False
    for key,tolerance in [('temperature',5),('feels_like',5),('humidity',20),('wind',12)]:
        value=current.get(key)
        if value is not None:
            if previous.get(key) is None or abs(value-previous[key])>tolerance:return False
    if current.get('precipitation') is not None:
        if previous.get('precipitation') is None or (current['precipitation']>0)!=(previous['precipitation']>0):return False
    return True


def compatible(candidate):
    if candidate.get('score') is None or candidate['score']<70 or candidate.get('penalties'):return False
    return all(value>=60 for key,value in candidate['components'].items() if key in ['temperature','weather','time','season','occasion','environment','projection','longevity'])


def recipe_label(recipe):
    return recipe['first']['name']+' + '+recipe['second']['name']


def recommendation(recipes,pair_wears,single_wears,candidates,context):
    if not candidates or candidates[0]['score'] is None:return None
    by_id={c['fragrance']['id']:c for c in candidates};winner=candidates[0]
    options=[]
    for recipe in recipes:
        ids=[recipe['first_id'],recipe['second_id']]
        if not recipe.get('available') or any(i not in by_id or not compatible(by_id[i]) for i in ids):continue
        history=[w for w in pair_wears if w['layering_id']==recipe['id'] and w.get('feedback')]
        history.sort(key=lambda w:w['created_at'],reverse=True)
        def positive(w):
            f=w['feedback'];return f['rating']>=4 and f['comparison']=='better together' and f['strength']=='perfect'
        # A fresh negative result takes precedence over older successes.
        if not history or not positive(history[0]):continue
        matches=[w for w in history if similar_context(context,w['snapshot']['context'])]
        matches=matches[:10]
        dates={datetime.fromisoformat(w['snapshot']['context']['now']).date() for w in matches if positive(w)}
        good=[w for w in matches if positive(w)]
        if len(dates)<3 or len(good)/len(matches)<.8:continue
        # Known observed duration must cover the current planned wear horizon.
        if any(w['feedback'].get('longevity') is not None and context.get('duration') is not None and w['feedback']['longevity']<context['duration'] for w in good):continue
        average=sum(w['feedback']['rating'] for w in matches)/len(matches)
        if average<4:continue
        if winner['fragrance']['id'] in ids:
            reason=f'You preferred this exact recipe to either fragrance alone on {len(good)} similar-condition wears across {len(dates)} days.'
            baseline=None
        else:
            baseline_wears=[w for w in single_wears if w['fragrance_id']==winner['fragrance']['id'] and w.get('feedback') and similar_context(context,w['snapshot']['context'])]
            if len(baseline_wears)<3:continue
            baseline=sum(w['feedback']['rating'] for w in baseline_wears)/len(baseline_wears)
            if average<baseline+.5:continue
            reason=f'Your pair rating averaged {average:.1f}/5 in similar conditions, versus {baseline:.1f}/5 for {winner["fragrance"]["name"]} worn alone.'
        options.append(dict(recipe=recipe,reason=reason,evidence_count=len(matches),positive_days=len(dates),average_rating=round(average,2),single_baseline=baseline,context=context))
    # Select at most one, using observed preference, never a synthetic blend score.
    return max(options,key=lambda o:(o['average_rating'],o['positive_days'],-o['recipe']['id'])) if options else None


def experiments(candidates,recipes):
    candidates=[c for c in candidates if compatible(c)][:10]
    saved={frozenset([r['first_id'],r['second_id']]) for r in recipes if r.get('available')}
    results=[]
    for i,a in enumerate(candidates):
        for b in candidates[i+1:]:
            first,second=a['fragrance'],b['fragrance']
            if frozenset([first['id'],second['id']]) in saved:continue
            accords=lambda f:{v['name'].lower() for v in f.get('metadata',{}).get('main_accords',[]) if v.get('name')}
            aa,bb=accords(first),accords(second);shared=aa&bb
            contrast=any(first.get('attributes',{}).get(k) is not None and second.get('attributes',{}).get(k) is not None and abs(first['attributes'][k]-second['attributes'][k])>=25 for k in ['freshness','richness'])
            if shared and aa!=bb and contrast:
                results.append(dict(first_id=first['id'],second_id=second['id'],reason='Shared accord: '+', '.join(sorted(shared)[:2])+'. Their source profiles differ in freshness or richness. This is a test idea, not evidence that they blend well.'))
    return results[:3]
