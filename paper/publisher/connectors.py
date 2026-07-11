from matplotlib.patches import FancyArrowPatch
def arrow(ax,start,end,theme,lw=1.25,muted=False):
    ax.add_patch(FancyArrowPatch(start,end,arrowstyle='-|>',mutation_scale=13,linewidth=lw,color=theme.muted if muted else theme.accent,shrinkA=6,shrinkB=6,connectionstyle='arc3,rad=0.0'))
