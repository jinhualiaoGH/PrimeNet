from .canvas import Canvas
from .shapes import draw_node, draw_container, Node
from .connectors import arrow
from .themes import get_theme
class Diagram:
    def __init__(self,title,subtitle=None,width=9.0,height=5.8,theme_name='primenet_light'):
        self.theme=get_theme(theme_name); self.canvas=Canvas(title,width,height,self.theme); self.ax=self.canvas.ax; self.canvas.title_text(subtitle); self.nodes={}
    def add_node(self,node,fontsize=9): self.nodes[node.id]=node; draw_node(self.ax,node,self.theme,fontsize); return node
    def add_nodes(self,nodes,fontsize=9):
        for n in nodes: self.add_node(n,fontsize)
        return nodes
    def connect(self,src_id,dst_id,start='bottom',end='top',muted=False): self.connect_nodes(self.nodes[src_id],self.nodes[dst_id],start,end,muted)
    def connect_nodes(self,src,dst,start='bottom',end='top',muted=False): arrow(self.ax,getattr(src,start),getattr(dst,end),self.theme,muted=muted)
    def container(self,x,y,w,h,label): return draw_container(self.ax,x,y,w,h,label,self.theme)
    def note(self,text,x=.5,y=.05,fontsize=8): self.ax.text(x,y,text,ha='center',va='center',fontsize=fontsize,color=self.theme.muted,style='italic')
    def save(self,outdir,name): self.canvas.save(outdir,name,dpi=self.theme.dpi)
