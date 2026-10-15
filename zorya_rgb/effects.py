"""Deterministic color frames; time is supplied by the daemon's monotonic clock."""
import colorsys
import math


def rgb(hex_color):
    return tuple(int(hex_color[i:i+2],16) for i in (1,3,5))


def frame(state,count,elapsed):
    if count<=0: return []
    if not state['on']: return [(0,0,0)]*count
    primary=rgb(state['color']); secondary=rgb(state['secondary_color'])
    phase=elapsed*state['speed']; brightness=state['brightness']/100
    effect=state['effect']; result=[]
    for i in range(count):
        scale=brightness
        if effect=='pulse':
            scale *= (1+math.cos(phase*2*math.pi))/2
            color=primary
        elif effect=='rainbow':
            color=tuple(v*255 for v in colorsys.hsv_to_rgb((phase/5+i/count)%1,1,1))
        elif effect=='gradient':
            weight=(math.sin(phase*2*math.pi/5+i/max(count-1,1)*math.pi-math.pi/2)+1)/2
            color=tuple(a+(b-a)*weight for a,b in zip(primary,secondary))
        else: color=primary
        result.append(tuple(max(0,min(255,round(v*scale))) for v in color))
    return result
