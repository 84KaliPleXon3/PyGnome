import warnings

import netCDF4 as nc4
import numpy as np

from gnome.utilities.geometry.cy_point_in_polygon import points_in_polys
from datetime import datetime, timedelta
from dateutil import parser
from colander import SchemaNode, Float, MappingSchema, drop, String, OneOf
from gnome.persist.base_schema import ObjType
from gnome.utilities import serializable
from gnome.movers import ProcessSchema

import pyugrid
import pysgrid


def tri_vector_field(filename=None, dataset=None):
    if dataset is None:
        dataset = nc4.Dataset(filename)

    nodes = np.ascontiguousarray(
        np.column_stack((dataset['lon'], dataset['lat']))).astype(np.double)
    faces = np.ascontiguousarray(np.array(dataset['nv']).T - 1)
    boundaries = np.ascontiguousarray(np.array(dataset['bnd'])[:, 0:2] - 1)
    neighbors = np.ascontiguousarray(np.array(dataset['nbe']).T - 1)
    edges = None
    grid = pyugrid.UGrid(nodes,
                         faces,
                         edges,
                         boundaries,
                         neighbors)
    grid.build_edges()
    u = pyugrid.UVar('u', 'node', dataset['u'])
    v = pyugrid.UVar('v', 'node', dataset['v'])
    time = Time(dataset['time'])
    variables = {'u':u, 'v':v}
    type = dataset.grid_type
    return VectorField(grid, time=time, variables=variables, type=type)


def ice_field(filename=None):
    gridset = None
    dataset = None

    dataset = nc4.Dataset(filename)

    time = Time(dataset['time'])
    w_u = pysgrid.variables.SGridVariable(data=dataset['water_u'])
    w_v = pysgrid.variables.SGridVariable(data=dataset['water_v'])
    i_u = pysgrid.variables.SGridVariable(data=dataset['ice_u'])
    i_v = pysgrid.variables.SGridVariable(data=dataset['ice_v'])
    a_u = pysgrid.variables.SGridVariable(data=dataset['air_u'])
    a_v = pysgrid.variables.SGridVariable(data=dataset['air_v'])
    i_thickness = pysgrid.variables.SGridVariable(
        data=dataset['ice_thickness'])
    i_coverage = pysgrid.variables.SGridVariable(data=dataset['ice_fraction'])

    grid = pysgrid.SGrid(node_lon=dataset['lon'],
                         node_lat=dataset['lat'])

    ice_vars = {'u': i_u,
                'v': i_v,
                'thickness': i_thickness,
                'coverage': i_coverage}
    water_vars = {'u': w_u,
                  'v': w_v, }
    air_vars = {'u': a_u,
                'v': a_v}

    dims = grid.node_lon.shape
    icefield = SField(grid, time=time, variables=ice_vars, dimensions=dims)
    waterfield = SField(grid, time=time, variables=water_vars, dimensions=dims)
    airfield = SField(grid, time=time, variables=air_vars, dimensions=dims)

    return (icefield, waterfield, airfield)


def curv_field(filename=None, dataset=None):
    if dataset is None:
        dataset = nc4.Dataset(filename)
    node_lon = dataset['lonc']
    node_lat = dataset['latc']
    u = dataset['water_u']
    v = dataset['water_v']
    dims = node_lon.dimensions[0] + ' ' + node_lon.dimensions[1]

    grid = pysgrid.SGrid(node_lon=node_lon,
                         node_lat=node_lat,
                         node_dimensions=dims)
    grid.u = pysgrid.variables.SGridVariable(data=u)
    grid.v = pysgrid.variables.SGridVariable(data=v)
    time = Time(dataset['time'])
    variables = {'u': grid.u,
                 'v': grid.v,
                 'time': time}
    return SField(grid, time=time, variables=variables)


def roms_field(filename=None, dataset=None):
    if dataset is None:
        dataset = nc4.Dataset(filename)

    grid = pysgrid.load_grid(dataset)

    time = Time(dataset['ocean_time'])
    u = grid.u
    v = grid.v
    u_mask = grid.mask_u
    v_mask = grid.mask_v
    r_mask = grid.mask_rho
    land_mask = grid.mask_psi
    variables = {'u': u,
                 'v': v,
                 'u_mask': u_mask,
                 'v_mask': v_mask,
                 'land_mask': land_mask,
                 'time': time}
    return SField(grid, time=time, variables=variables)


class VectorFieldSchema(ObjType, ProcessSchema):
    uncertain_duration = SchemaNode(Float(), missing=drop)
    uncertain_time_delay = SchemaNode(Float(), missing=drop)
    filename = SchemaNode(String(), missing=drop)
    topology_file = SchemaNode(String(), missing=drop)
    current_scale = SchemaNode(Float(), missing=drop)
    uncertain_along = SchemaNode(Float(), missing=drop)
    uncertain_cross = SchemaNode(Float(), missing=drop)


class VectorField(object):
    '''
    This class takes a netCDF file containing current or wind information on an unstructured grid
    and provides an interface to retrieve this information.
    '''

    def __init__(self, grid,
                 time=None,
                 variables=None,
                 name=None,
                 type=None,
                 velocities=None,
                 appearance={}
                 ):
        self.grid = grid
#         if grid.face_face_connectivity is None:
#             self.grid.build_face_face_connectivity()
        self.grid_type = type
        self.time = time
        self.variables = variables
        for k, v in self.variables.items():
            setattr(self, k, v)

        if not hasattr(self, 'velocities'):
            self.velocities = velocities
        self._appearance = {}
        self.set_appearance(**appearance)

    def set_appearance(self, **kwargs):
        self._appearance.update(kwargs)

    @property
    def appearance(self):
        d = {'on': False,
             'color': 'grid_1',
             'width': 1,
             'filled': False,
             'mask': None,
             'n_size': 2,
             'type': 'unstructured'}
        d.update(self._appearance)
        return d

    @property
    def nodes(self):
        return self.grid.nodes

    @property
    def faces(self):
        return self.grid.faces

    @property
    def triangles(self):
        return self.grid.nodes[self.grid.faces]

    def interpolated_velocities(self, time, points):
        """
        Returns the velocities at each of the points at the specified time, using interpolation
        on the nodes of the triangle that the point is in.
        :param time: The time in the simulation
        :param points: a numpy array of points that you want to find interpolated velocities for
        :return: interpolated velocities at the specified points
        """

        t_alphas = self.time.interp_alpha(time)
        t_index = self.time.indexof(time)

        u0 = self.u[t_index]
        u1 = self.u[t_index+1]
        ut = u0 + (u1 - u0) * t_alphas
        v0 = self.v[t_index]
        v1 = self.v[t_index+1]
        vt = v0 + (v1 - v0) * t_alphas

        u_vels = self.grid.interpolate_var_to_points(points, ut)
        v_vels = self.grid.interpolate_var_to_points(points, vt)

        vels = np.ma.column_stack((u_vels, v_vels))
        return vels

    def interpolate(self, time, points, field):
        """
        Returns the velocities at each of the points at the specified time, using interpolation
        on the nodes of the triangle that the point is in.
        :param time: The time in the simulation
        :param points: a numpy array of points that you want to find interpolated velocities for
        :param field: the value field that you want to interpolate over. 
        :return: interpolated velocities at the specified points
        """
        indices = self.grid.locate_faces(points)
        pos_alphas = self.grid.interpolation_alphas(points, indices)
        # map the node velocities to the faces specified by the points
        t_alpha = self.time.interp_alpha(time)
        t_index = self.time.indexof(time)
        f0 = field[t_index]
        f1 = field[t_index + 1]
        node_vals = f0 + (f1 - f0) * t_alpha
        time_interp_vels = node_vels[self.grid.faces[indices]]

        return np.sum(time_interp_vels * pos_alphas[:, :, np.newaxis], axis=1)

    def get_edges(self, bounds=None):
        """

        :param bounds: Optional bounding box. Expected is lower left corner and top right corner in a tuple
        :return: array of pairs of lon/lat points describing all the edges in the grid, or only those within
        the bounds, if bounds is specified.
        """
        return self.grid.edges
        if bounds is None:
            return self.grid.nodes[self.grid.edges]
        else:
            lines = self.grid.nodes[self.grid.edges]

            def within_bounds(line, bounds):
                pt1 = (bounds[0][0] <= line[0, 0] * line[0, 0] <= bounds[1][0] and
                       bounds[0][1] <= line[0, 1] * line[:, 0, 1] <= bounds[1][1])
                pt2 = (bounds[0][0] <= line[1, 0] <= bounds[1][0] and
                       bounds[0][1] <= line[1, 1] <= bounds[1][1])
                return pt1 or pt2
            pt1 = ((bounds[0][0] <= lines[:, 0, 0]) * (lines[:, 0, 0] <= bounds[1][0]) *
                   (bounds[0][1] <= lines[:, 0, 1]) * (lines[:, 0, 1] <= bounds[1][1]))
            pt2 = ((bounds[0][0] <= lines[:, 1, 0]) * (lines[:, 1, 0] <= bounds[1][0]) *
                   (bounds[0][1] <= lines[:, 1, 1]) * (lines[:, 1, 1] <= bounds[1][1]))
            return lines[pt1 + pt2]

    def masked_nodes(self, time, variable):
        """
        This allows visualization of the grid nodes with relation to whether the velocity is masked or not.
        :param time: a time within the simulation
        :return: An array of all the nodes, masked with the velocity mask.
        """
        if hasattr(variable, 'name') and variable.name in self.variables:
            if time < self.time.max_time:
                return np.ma.array(self.grid.nodes, mask=variable[self.time.indexof(time)].mask)
            else:
                return np.ma.array(self.grid.nodes, mask=variable[self.time.indexof(self.time.max_time)].mask)
        else:
            variable = np.array(variable, dtype=bool).reshape(-1, 2)
            return np.ma.array(self.grid.nodes, mask=variable)


class Time(object):

    def __init__(self, data, base_dt_str=None):
        """

        :param data: A netCDF, biggus, or dask source for time data
        :return:
        """
        self.time = nc4.num2date(data[:], units=data.units)

    @property
    def min_time(self):
        return self.time[0]

    @property
    def max_time(self):
        return self.time[-1]

    def get_time_array(self):
        return self.time[:]

    def time_in_bounds(self, time):
        return not time < self.min_time or time > self.max_time

    def valid_time(self, time):
        if time < self.min_time or time > self.max_time:
            raise ValueError('time specified ({0}) is not within the bounds of the time ({1} to {2})'.format(
                time.strftime('%c'), self.min_time.strftime('%c'), self.max_time.strftime('%c')))

    def indexof(self, time):
        '''
        Returns the index of the provided time with respect to the time intervals in the file.
        :param time:
        :return:
        '''
        self.valid_time(time)
        index = np.searchsorted(self.time, time) - 1
        return index

    def interp_alpha(self, time):
        i0 = self.indexof(time)
        t0 = self.time[i0]
        t1 = self.time[i0 + 1]
        return (time - t0).total_seconds() / (t1 - t0).total_seconds()


class SField(VectorField):

    def __init__(self, grid,
                 time=None,
                 variables=None,
                 name=None,
                 type=None,
                 appearance={}
                 ):
        self.grid = grid
        self.time = time
        self.variables = variables
        for k, v in self.variables.items():
            setattr(self, k, v)
        self.grid_type = type

        self._appearance = {}
        self.set_appearance(**appearance)

    @classmethod
    def verify_variables(self):
        '''
        This function verifies that the SField is built with enough information
        to accomplish it's goal. For example a subclass that works with water conditions should
        verify that the water temperature, salinity, u-velocity, v-velocity, etc are all present.


        In subclasses, this should be overridden
        '''
        pass

    def set_appearance(self, **kwargs):
        self._appearance.update(kwargs)

    @property
    def appearance(self):
        d = {'on': False,
             'color': 'grid_1',
             'width': 1,
             'filled': False,
             'mask': None,
             'n_size': 2,
             'type': 'curvilinear'}
        d.update(self._appearance)
        return d

    def interpolate_var(self, points, variable, time, depth=None, memo=True, _hash=None):
        '''
        Interpolates an arbitrary variable to the points specified at the time specified
        '''
        #         points = np.ascontiguousarray(points)
        memo = True
        if _hash is None:
            _hash = self.grid._hash_of_pts(points)
        t_alphas = self.time.interp_alpha(time)
        t_index = self.time.indexof(time)

        s1 = [t_index]
        s2 = [t_index + 1]
        if len(variable.shape) == 4:
            s1.append(depth)
            s2.append(depth)

        v0 = self.grid.interpolate_var_to_points(points, variable, slices=s1, memo=memo, _hash=_hash)
        v1 = self.grid.interpolate_var_to_points(points, variable, slices=s2, memo=memo, _hash=_hash)

        vt = v0 + (v1 - v0) * t_alphas

        return vt

    def interp_alphas(self, points, grid=None, indices=None, translation=None):
        '''
        Find the interpolation alphas for the four points of the cells that contains the points
        This function is meant to be a universal way to get these alphas, including translating across grids

        If grid is not specified, it will default to the grid contained in self, ignoring any translation specified

        If the grid is specified and indicies is not, it will use the grid's cell location
        function to find the indices of the points. This may incur extra memory usage if the
        grid needs to construct a cell_tree

        If the grid is specified and indices is specified, it will use those indices and points to
        find interpolation alphas. If translation is specified, it will translate the indices
        beforehand.
        :param points: Numpy array of 2D points
        :param grid: The SGrid object that you want to interpolate over
        :param indices: Numpy array of the x,y indices of each point
        :param translation: String to specify an index translation.
        '''
        if grid is None:
            grid = self.grid
            pos_alphas = grid.interpolation_alphas(points, indices)
            return pos_alphas
        if indices is None:
            if translation is not None:
                warnings.warn(
                    "indices not provided, translation ignored", UserWarning)
                translation = None
            indices = grid.locate_faces(points)
        if translation is not None:
            indices = pysgrid.utils.translate_index(
                points, indices, grid, translation)
        pos_alphas = grid.interpolation_alphas(points, indices)
        return pos_alphas

    def interpolated_velocities(self, time, points, indices=None, alphas=None, depth=-1):
        '''
        Finds velocities at the points at the time specified, interpolating in 2D
        over the u and v grids to do so.
        :param time: The time in the simulation
        :param points: a numpy array of points that you want to find interpolated velocities for
        :param indices: Numpy array of indices of the points, if already known.
        :return: interpolated velocities at the specified points
        '''

        mem = True
        ind = indices
        t_alphas = self.time.interp_alpha(time)
        t_index = self.time.indexof(time)

        s1 = [t_index]
        s2 = [t_index + 1]
        s3 = [t_index]
        s4 = [t_index + 1]
        if len(self.u.shape) == 4:
            s1.append(depth)
            s2.append(depth)
            s3.append(depth)
            s4.append(depth)

        sg = False

        u0 = self.grid.interpolate_var_to_points(points, self.u, slices=s1, slice_grid=sg, memo=mem)
        u1 = self.grid.interpolate_var_to_points(points, self.u, slices=s2, slice_grid=sg, memo=mem)

        v0 = self.grid.interpolate_var_to_points(points, self.v, slices=s3, slice_grid=sg, memo=mem)
        v1 = self.grid.interpolate_var_to_points(points, self.v, slices=s4, slice_grid=sg, memo=mem)

        u_vels = u0 + (u1 - u0) * t_alphas
        v_vels = v0 + (v1 - v0) * t_alphas

        if self.grid.angles is not None:
            angs = self.grid.interpolate_var_to_points(points, self.grid.angles, slices=None, slice_grid=False, memo=mem)
            u_rot = u_vels*np.cos(angs) - v_vels*np.sin(angs)
            v_rot = u_vels*np.sin(angs) + v_vels*np.cos(angs)
#             rotations = np.array(
#                 ([np.cos(angs), -np.sin(angs)], [np.sin(angs), np.cos(angs)]))

#             return np.matmul(rotations.T, vels[:, :, np.newaxis]).reshape(-1, 2)
        vels = np.ma.column_stack((u_rot, v_rot))
        return vels

    def get_edges(self, bounds=None):
        """

        :param bounds: Optional bounding box. Expected is lower left corner and top right corner in a tuple
        :return: array of pairs of lon/lat points describing all the edges in the grid, or only those within
        the bounds, if bounds is specified.
        """
        return self.grid.get_grid()
