"""Pure, deterministic scoring. Scores are suitability estimates, not probabilities."""
from datetime import datetime
import math

WEIGHTS = dict(temperature=15, weather=12, occasion=15, environment=10,
               time=8, season=5, projection=8, longevity=8, preference=10,
               history=5, rotation=4)
ATTRIBUTES = ['sweetness','freshness','warmth','spiciness','woodiness','citrus',
              'aquatic','floral','powderiness','richness','projection','versatility','formality']

def clamp(value):
    return max(0, min(100, value))

def personal_constraints(fragrance,context):
    limits=fragrance.get('limits') or {};constraints=[];temp=context.get('temperature')
    if temp is not None:
        if limits.get('min_temperature') is not None and temp<limits['min_temperature']:constraints.append(f'Your rule: do not suggest below {limits["min_temperature"]:g}°C (currently {temp:g}°C).')
        if limits.get('max_temperature') is not None and temp>limits['max_temperature']:constraints.append(f'Your rule: do not suggest above {limits["max_temperature"]:g}°C (currently {temp:g}°C).')
    if limits.get('avoid_confined') and context.get('environment')=='confined':constraints.append('Your rule: do not suggest in confined spaces.')
    return constraints

def community_suitability(fragrance,dimension,label):
    if dimension in fragrance.get('overrides',[]):return None
    data=fragrance.get('metadata',{}).get('community',{}).get(dimension,{})
    values=data.get('values',{})
    aliases={'work':'professional','party':'night out','evening':'night','morning':'day','afternoon':'day'}
    value=values.get(label,values.get(aliases.get(label)))
    return value*100 if value is not None else None

def score(fragrance, context, preferences, wears, weights=None):
    a = fragrance.get('attributes', {})
    components, penalties = {}, []
    temp = context.get('temperature')
    if temp is not None and context.get('feels_like') is not None:
        temp = .7*temp + .3*context['feels_like']
    known = lambda key: a.get(key) is not None
    supplied = lambda value: value is not None and str(value).strip().lower() not in ['', 'unknown', 'unavailable', 'not listed', 'automatic']
    environment = context.get('environment')
    if temp is not None and known('warmth') and known('freshness'):
        # Balance both attributes: moderate amber/sweetness must not make a very
        # fresh citrus profile look almost ideally warm at single-digit Celsius.
        desired = clamp((26-temp)*5)
        thermal_profile = (a['warmth']+100-a['freshness'])/2
        components['temperature'] = clamp(100-abs(thermal_profile-desired))
    humidity_relevant = temp is not None and temp>=20 and context.get('humidity') is not None and known('freshness')
    if humidity_relevant:
        components['weather'] = clamp(95-max(0,context['humidity']-65)*max(0,50-a['freshness'])/60)
    if environment=='outdoor' and known('projection') and (context.get('wind') is not None or context.get('precipitation') is not None):
        exposure=min(15,max(0,(context.get('wind') or 0)-15)*.3+(context.get('precipitation') or 0)*2)
        components['weather']=clamp(components.get('weather',100)-exposure*max(0,60-a['projection'])/60)
    occasion = context.get('occasion')
    community_occasion=community_suitability(fragrance,'occasions',occasion)
    if supplied(occasion) and community_occasion is not None:components['occasion']=community_occasion
    elif supplied(occasion) and fragrance.get('occasions'):
        components['occasion'] = 96 if occasion in fragrance['occasions'] else (78 if occasion == 'casual' else 55)
    projection = a.get('projection')
    preferred_projection=preferences.get('projection')
    if projection is not None and preferred_projection is not None:
        components['projection'] = clamp(100-abs(projection-preferred_projection))
    if projection is not None and environment in ['confined','indoor','outdoor']:
        target = 35 if environment=='confined' else 65 if environment=='outdoor' else preferred_projection
        if target is not None:components['environment'] = clamp(100-max(0,projection-target)*1.3)
    community_time=community_suitability(fragrance,'dayparts',context.get('daypart'))
    if supplied(context.get('daypart')) and community_time is not None:components['time']=community_time
    elif supplied(context.get('daypart')) and fragrance.get('dayparts'):
        components['time'] = 96 if context.get('daypart') in fragrance['dayparts'] else 55
    community_season=community_suitability(fragrance,'seasons',context.get('season'))
    if supplied(context.get('season')) and community_season is not None:components['season']=community_season
    elif fragrance.get('seasons') and supplied(context.get('season')):
        components['season'] = 90 if context['season'] in fragrance['seasons'] else 65
    fw = [w for w in wears if w['fragrance_id']==fragrance['id']]
    observations = [w['feedback']['longevity'] for w in fw if w.get('feedback') and w['feedback'].get('longevity') is not None]
    longevity = fragrance.get('personal_longevity') or fragrance.get('longevity')
    community_rating=fragrance.get('metadata',{}).get('community_rating',{})
    sample_count=community_rating.get('count')
    performance_count=fragrance.get('metadata',{}).get('performance',{}).get('longevity',{}).get('sample_count')
    prior_count=max(5,min(25,5+math.log10(1+(performance_count or sample_count or 0))*4)) if fragrance.get('metadata') else 5
    if observations:
        # Strong community evidence uses up to 25 equivalent prior observations.
        longevity = ((longevity or sum(observations)/len(observations))*prior_count+sum(observations))/(prior_count+len(observations))
    if longevity is not None and context.get('duration') is not None:
        components['longevity'] = clamp(100-max(0,context['duration']-longevity)*18)
    if fragrance.get('rating') is not None:
        components['preference'] = fragrance['rating']*20
        components['preference'] = clamp(components['preference'] + (preferences.get('favorite_bias',4) if fragrance.get('favorite') else 0))
    feedback = [w['feedback']['rating'] for w in fw if w.get('feedback') and 'rating' in w['feedback']]
    community_value=community_rating.get('value')
    community_prior=community_value*20 if community_value is not None else None
    if feedback:
        components['history'] = (community_prior*prior_count+sum(r*20 for r in feedback))/(prior_count+len(feedback)) if community_prior is not None else sum(r*20 for r in feedback)/len(feedback)
    elif community_prior is not None:
        components['history'] = community_prior
    recent = [w for w in fw if 0 <= (datetime.fromisoformat(context['now'])-datetime.fromisoformat(w['created_at'])).total_seconds()/86400 < 7]
    components['rotation'] = max(0,100-len(recent)*30*preferences.get('variety',1))
    if temp is not None and temp>=30 and a.get('sweetness',0)>=75 and a.get('richness',0)>=75:
        penalties.append(dict(amount=30, reason='A dense, sweet profile in extreme heat.'))
    if environment=='confined' and projection is not None and projection>=75:
        penalties.append(dict(amount=30, reason='Strong projection in a confined setting.'))
    if longevity is not None and context.get('duration') is not None and context['duration']>=6 and longevity<context['duration']/2:
        penalties.append(dict(amount=20, reason='Estimated longevity covers less than half your plans.'))
    if occasion in ['formal','wedding','interview'] and known('formality') and a['formality']<30:
        penalties.append(dict(amount=20, reason='A casual profile for a formal occasion.'))
    weights = weights or WEIGHTS
    effective = {k:weights.get(k,0) for k in components}
    total = sum(effective.values())
    # Sparse metadata must not let rotation dominate the remaining weights.
    rotation_share = min(.04, effective.get('rotation',0)/total) if total else 0
    nonrotation = sum(v for k,v in effective.items() if k!='rotation')
    contributions = {k: (components[k]*rotation_share if k=='rotation' else components[k]*effective[k]/nonrotation*(1-rotation_share) if nonrotation else 0) for k in components}
    shares={k:100*(rotation_share if k=='rotation' else effective[k]/nonrotation*(1-rotation_share) if nonrotation else 0) for k in components}
    base = sum(contributions.values()) if nonrotation else None
    final = round(clamp(base-sum(p['amount'] for p in penalties))) if base is not None else None
    # A high seasonal rank, popularity or longevity cannot turn a weak measured
    # temperature fit into a strong overall recommendation. Unknown fit is left
    # out entirely, and an explicitly disabled temperature weight stays disabled.
    temperature_limit=None
    if final is not None and effective.get('temperature',0)>0 and components['temperature']<60:
        ceiling=round(100*(components['temperature']/60)**1.25)
        if final>ceiling:
            temperature_limit=dict(temperature=round(temp,1),fit=round(components['temperature'],1),ceiling=ceiling,amount=final-ceiling,
                                   reason=f'Weak temperature fit at {temp:.1f}°C limits the overall score to {ceiling}/100.')
            penalties.append(dict(amount=final-ceiling,reason=temperature_limit['reason'],type='temperature_limit'))
            final=ceiling
    if base is None:
        contributions={key:0 for key in components};shares={key:0 for key in components}
    constraints=personal_constraints(fragrance,context)
    if constraints:
        penalties.append(dict(amount=final or 0,reason=' '.join(constraints),type='personal_boundary'));final=0
    coverage = sum(WEIGHTS[k] for k in components if k not in ['history','rotation','preference'])/81
    certainty = .5*min(1,coverage)+.2*bool(context.get('weather'))+.15*context.get('context_certainty',.4)+.15*min(1,len(feedback)/5)
    if fragrance.get('metadata'):
        # A tiny vote sample and inferred attributes reduce reliability. Unknown counts
        # remain unknown and never become a guessed popularity-derived vote count.
        reliability=.5+.5*min(1,math.log10(1+(sample_count or 0))/4) if sample_count is not None else .65
        inferred=sum(1 for v in fragrance.get('provenance',{}).values() if v.get('source')=='inferred')
        personal_support=min(1,len(feedback)/20)
        certainty=clamp(certainty*100-12*(1-reliability)*(1-personal_support)-min(6,inferred*.5))/100
    if final is None:certainty=0
    confidence = 'High' if certainty>=.8 else 'Medium' if certainty>=.5 else 'Low'
    sprays = max(1,min(5,round(4-projection/35))) if projection is not None else None
    strength_feedback = [w['feedback'].get('strength') for w in fw if w.get('feedback')]
    if sprays is not None and len(strength_feedback)>=3:
        sprays = max(1,min(5,sprays + round((strength_feedback.count('too weak')-strength_feedback.count('too strong'))/len(strength_feedback))))
    if sprays is not None and environment=='confined': sprays = min(sprays,2)
    strongest = sorted((k for k in components if k not in ['history','rotation','preference'] and effective.get(k,0)>0),key=lambda k:components[k],reverse=True)[:2]
    reasons = {'temperature':'Its profile suits temperatures across your wear horizon.', 'weather':'Its freshness is a good fit for the humidity.', 'occasion':f'It fits your {occasion} plans.', 'environment':'Its projection suits your surroundings.', 'projection':'Its projection fits your preferred presence.', 'time':f'It suits the {context.get("daypart")}.', 'season':f'It fits the {context.get("season")} season.', 'longevity':'Its estimated longevity covers your plans.'}
    omitted={k:'Not used: the context or fragrance information for this factor is unknown.' for k in WEIGHTS if k not in components}
    if 'weather' not in components and temp is not None and temp<20:
        omitted['weather']='Not used: humidity freshness scoring applies to warm weather; no known outdoor exposure is being scored.'
    explanation = ' '.join(reasons[k] for k in strongest if components[k]>=75)
    if not explanation: explanation = 'This is the closest fit among the attributes you have supplied.'
    if final is None: explanation = 'Not enough known information to score this fragrance.'
    if recent and final is not None: explanation += ' Recent wears slightly reduce its rotation score.'
    if penalties: explanation += ' '+penalties[0]['reason']
    if temperature_limit and penalties[0].get('type')!='temperature_limit':explanation+=' '+temperature_limit['reason']
    if temperature_limit:explanation = temperature_limit['reason']+' Other factors do not make it a strong temperature match.'
    if constraints:explanation=' '.join(constraints)
    if confidence=='Low' and not constraints: explanation += ' Add more metadata or context to improve reliability.'
    return dict(fragrance=fragrance, score=final, confidence=confidence, certainty=round(certainty*100),
                components={k:round(v,1) for k,v in components.items()}, weights=effective,shares={k:round(v,3) for k,v in shares.items()},excluded=bool(constraints),constraints=constraints,
                contributions={k:round(contributions[k],2) for k in components},
                base=round(base,2) if base is not None else None, penalties=penalties, sprays=sprays,
                personal_longevity=longevity, explanation=explanation, omitted=omitted,temperature_limit=temperature_limit,
                community_prior=dict(rating=community_value,rating_count=sample_count,equivalent_observations=round(prior_count,1)))

def rank(collection, context, preferences, wears):
    result = [score(f,context,preferences,wears,preferences.get('weights')) for f in collection]
    return sorted(result,key=lambda r:(r.get('excluded',False),-(r['score'] if r['score'] is not None else -1),r['fragrance']['id']))
