from dataclasses import dataclass
from matplotlib.patches import FancyBboxPatch
@dataclass
class Node:
    id:str; label:str; x:float=0; y:float=0; w:float=0.18; h:float=0.10; kind:str='default'
    @property
    def center(self): return (self.x+self.w/2,self.y+self.h/2)
    @property
    def top(self): return (self.x+self.w/2,self.y+self.h)
    @property
    def bottom(self): return (self.x+self.w/2,self.y)
    @property
    def left(self): return (self.x,self.y+self.h/2)
    @property
    def right(self): return (self.x+self.w,self.y+self.h/2)
def colors_for(node,theme):
    if node.kind=='evidence': return '#FFF8E5', theme.accent2
    if node.kind=='foundation': return '#EAF4FB', theme.accent
    if node.kind=='neutral': return '#F7F9FA', theme.container_edge
    return theme.box_fill, theme.box_edge
def draw_node(ax,node,theme,fontsize=9):
    fill,edge=colors_for(node,theme)
    patch=FancyBboxPatch((node.x,node.y),node.w,node.h,boxstyle='round,pad=0.015,rounding_size=0.035',linewidth=1.4,edgecolor=edge,facecolor=fill)
    ax.add_patch(patch); ax.text(node.x+node.w/2,node.y+node.h/2,node.label,ha='center',va='center',fontsize=fontsize,color=theme.ink,linespacing=1.2); return patch
def draw_container(ax,x,y,w,h,label,theme):
    patch=FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.02,rounding_size=0.04',linewidth=1.1,edgecolor=theme.container_edge,facecolor=theme.container_fill,alpha=.95)
    ax.add_patch(patch); ax.text(x+.02,y+h-.035,label,ha='left',va='top',fontsize=9,fontweight='bold',color=theme.muted); return patch
