from pathlib import Path
import matplotlib.pyplot as plt
class Canvas:
    def __init__(self,title,width=9.0,height=5.8,theme=None):
        self.title=title; self.theme=theme
        plt.rcParams['font.family']=theme.font_family if theme else 'DejaVu Sans'
        self.fig,self.ax=plt.subplots(figsize=(width,height)); self.ax.set_xlim(0,1); self.ax.set_ylim(0,1); self.ax.axis('off')
        if theme: self.fig.patch.set_facecolor(theme.background); self.ax.set_facecolor(theme.background)
    def title_text(self,subtitle=None):
        self.ax.text(0.5,0.965,self.title,ha='center',va='top',fontsize=16,fontweight='bold',color=self.theme.ink)
        if subtitle: self.ax.text(0.5,0.915,subtitle,ha='center',va='top',fontsize=9,color=self.theme.muted)
    def save(self,outdir,name,dpi=260):
        outdir=Path(outdir); outdir.mkdir(parents=True,exist_ok=True)
        self.fig.savefig(outdir/f'{name}.png',dpi=dpi,bbox_inches='tight',facecolor=self.fig.get_facecolor())
        self.fig.savefig(outdir/f'{name}.svg',bbox_inches='tight',facecolor=self.fig.get_facecolor())
        plt.close(self.fig)
