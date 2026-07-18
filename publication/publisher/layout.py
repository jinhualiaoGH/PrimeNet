from .shapes import Node
def vertical_stack(labels,x=.38,y_top=.78,w=.24,h=.085,gap=.075,prefix='v',kind='default'):
    nodes=[]; y=y_top
    for i,label in enumerate(labels,1): nodes.append(Node(f'{prefix}{i}',label,x=x,y=y,w=w,h=h,kind=kind)); y-=h+gap
    return nodes
def horizontal_stack(labels,x_left=.08,y=.50,w=.16,h=.09,gap=.045,prefix='h',kind='default'):
    nodes=[]; x=x_left
    for i,label in enumerate(labels,1): nodes.append(Node(f'{prefix}{i}',label,x=x,y=y,w=w,h=h,kind=kind)); x+=w+gap
    return nodes
def grid(labels,cols=3,x0=.08,y0=.62,w=.22,h=.10,xgap=.055,ygap=.10,prefix='g',kind='default'):
    nodes=[]
    for idx,label in enumerate(labels):
        row,col=divmod(idx,cols); nodes.append(Node(f'{prefix}{idx+1}',label,x=x0+col*(w+xgap),y=y0-row*(h+ygap),w=w,h=h,kind=kind))
    return nodes
def center_node(label,y=.08,w=.42,h=.09,prefix='c',kind='foundation'): return Node(prefix,label,x=.5-w/2,y=y,w=w,h=h,kind=kind)
