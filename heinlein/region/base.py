from abc import abstractmethod
from typing import Any
from shapely.affinity import translate

class BaseRegion:

    def __init__(self, geometry, *args, **kwargs):
        """
        Base region object
        """
        self._geometry = geometry
        self._cache = {}
        self.check_for_edges()


    def intersects(self, other) -> bool:
        for geo in self._geometries:
            for other_geo in other._geometries:
                if geo.intersects(other_geo):
                    return True
        return False

    def center(self, *args, **kwargs):
        pass
    def cache(self, ref: Any, dtype: str) -> None:
        self._cache.update({dtype: ref})

    def get_data(self, handlers: dict, paths: dict, data: dict) -> None:
        for type, handler in handlers.items():
            try:
                d = self._cache[type]
            except KeyError:
                d = handler(paths[type], self)
                self._cache.update({type: d})
            data[type].append(d)
    
    def check_for_edges(self, *args, **kwargs):
        bounds = self._geometry.bounds
        x_min, y_min, x_max, y_max = bounds

        x_edge = BaseRegion.check_x_edge(x_min, x_max)
        y_edge = BaseRegion.chcek_y_edge(y_min, y_max)
        self._edge_overlap = (x_edge, y_edge)
        if any(self._edge_overlap):
            self.build_wrapped_regions()
        else:
            self._geometries = [self._geometry]

    @abstractmethod
    def build_wrapped_regions(self, *args, **kwargs):
        pass        

    @staticmethod
    def check_x_edge(minx, maxx):
        dx = maxx - minx

        maxx_r = (maxx + 90) % 360
        minx_r = (minx + 90) % 360

        dx_r = maxx_r - minx_r
        return (dx_r < 0) and (abs(dx_r) < abs(dx))


    @staticmethod
    def chcek_y_edge(minx, maxx):
        dx = maxx - minx

        maxx_r = (maxx - 45) % 360
        minx_r = (minx - 45) % 360

        dx_r = maxx_r - minx_r

        return (dx_r < 0) and (abs(dx_r) < abs(dx))
