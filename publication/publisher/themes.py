from dataclasses import dataclass
@dataclass(frozen=True)
class Theme:
    name:str; font_family:str; background:str; ink:str; muted:str; accent:str; accent2:str; box_fill:str; box_edge:str; container_fill:str; container_edge:str; table_header_fill:str; dpi:int=260
PRIMENET_LIGHT=Theme('primenet_light','DejaVu Sans','#FFFFFF','#1F2933','#52616B','#1F77B4','#F0B429','#F8FBFD','#1F77B4','#F3F6F8','#9FB3C8','#EAF4FB')
def get_theme(name=None): return PRIMENET_LIGHT
