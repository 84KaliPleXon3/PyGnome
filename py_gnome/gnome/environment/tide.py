"""
module contains objects that contain weather related data. For example,
the Wind object defines the Wind conditions for the spill
"""
import string
import os
import copy

from colander import SchemaNode, String, Float, drop

import gnome
from gnome.utilities.convert import tsformat
from gnome.utilities.inf_datetime import InfDateTime
from gnome.utilities.serializable import Serializable, Field

from .environment import Environment
from gnome.persist import base_schema

# TODO: The name 'convert' is doubly defined as
#       unit_conversion.convert and...
#       gnome.utilities.convert
#       This will inevitably cause namespace collisions.
#       CHB-- I don't think that's a problem -- that's what namespaces are for!

from gnome.cy_gnome.cy_ossm_time import CyTimeseries
from gnome.cy_gnome.cy_shio_time import CyShioTime


class TideSchema(base_schema.ObjType):
    'Tide object schema'
    filename = SchemaNode(String(), missing=drop)

    scale_factor = SchemaNode(Float(), missing=drop)

    name = 'tide'


class Tide(Environment, Serializable):

    """
    todo: baseclass called ScaleTimeseries (or something like that)
    ScaleCurrent
    Define the tide for a spill

    Currently, this internally defines and uses the CyShioTime object, which is
    a cython wrapper around the C++ Shio object
    """
    _ref_as = 'tide'
    _state = copy.deepcopy(Environment._state)
    _schema = TideSchema

    # add 'filename' as a Field object
    _update = ['scale_factor']
    _create = []
    _create.extend(_update)
    _state.add(update=_update, save=_create)
    _state.add_field(Field('filename', save=True, read=True, isdatafile=True,
                           test_for_eq=False))

    def __init__(self,
                 filename,
                 yeardata=os.path.join(os.path.dirname(gnome.__file__),
                                       'data', 'yeardata'),
                 **kwargs):
        """
        Tide information can be obtained from a filename or set as a
        timeseries (timeseries is NOT TESTED YET)

        It requires one of the following to initialize:

              1. 'timeseries' assumed to be in 'uv' format
                 (NOT TESTED/IMPLEMENTED OR USED YET)
              2. a 'filename' containing a header that defines units amongst
                 other meta data

        :param timeseries: numpy array containing tide data
        :type timeseries: numpy.ndarray with dtype=datetime_value_1d
        :param units: units associated with the timeseries data. If 'filename'
            is given, then units are read in from the filename.
            unit_conversion - NOT IMPLEMENTED YET
        :type units=None:  (Optional) string, for example:
            'knot', 'meter per second', 'mile per hour' etc
        :param filename: path to a long wind filename from which to read
            wind data
        :param yeardata='gnome/data/yeardata/': path to yeardata used for Shio
            data.

        """
        # define locally so it is available even for OSSM files,
        # though not used by OSSM files
        self._yeardata = None
        self.cy_obj = self._obj_to_create(filename)
        # self.yeardata = os.path.abspath( yeardata ) # set yeardata
        self.yeardata = yeardata  # set yeardata
        self.name = kwargs.pop('name', os.path.split(self.filename)[1])
        self.scale_factor = kwargs.get('scale_factor',
                                       self.cy_obj.scale_factor)

        kwargs.pop('scale_factor', None)
        super(Tide, self).__init__(**kwargs)

    @property
    def data_start(self):
        return InfDateTime("-inf")

    @property
    def data_stop(self):
        return InfDateTime("inf")

    @property
    def yeardata(self):
        return self._yeardata

    @yeardata.setter
    def yeardata(self, value):
        """
        only relevant if underlying cy_obj is CyShioTime
        """
        if not os.path.exists(value):
            raise IOError('Path to yeardata files does not exist: '
                          '{0}'.format(value))

        # set private variable and also shio object's yeardata path
        self._yeardata = value

        if isinstance(self.cy_obj, CyShioTime):
            self.cy_obj.set_shio_yeardata_path(value)

    filename = property(lambda self: (self.cy_obj.filename, None
                                      )[self.cy_obj.filename == ''])

    scale_factor = property(lambda self:
                            self.cy_obj.scale_factor, lambda self, val:
                            setattr(self.cy_obj, 'scale_factor', val))

    def _obj_to_create(self, filename):
        """
        open file, read a few lines to determine if it is an ossm file
        or a shio file
        """
        # mode 'U' means universal newline support
        fh = open(filename, 'rU')

        lines = [fh.readline() for i in range(4)]

        if len(lines[1]) == 0:
            # look for \r for lines instead of \n
            lines = string.split(lines[0], '\r', 4)

        if len(lines[1]) == 0:
            # if this is still 0, then throw an error!
            raise ValueError('This does not appear to be a valid file format '
                             'that can be read by OSSM or Shio to get '
                             'tide information')

        # look for following keywords to determine if it is a Shio or OSSM file
        shio_file = ['[StationInfo]', 'Type=', 'Name=', 'Latitude=']

        if all([shio_file[i] == (lines[i])[:len(shio_file[i])]
                for i in range(4)]):
            return CyShioTime(filename)
        elif len(string.split(lines[3], ',')) == 7:
            # maybe log / display a warning that v=0 for tide file and will be
            # ignored
            # if float( string.split(lines[3],',')[-1]) != 0.0:
            return CyTimeseries(filename, file_format=tsformat('uv'))
        else:
            raise ValueError('This does not appear to be a valid file format '
                             'that can be read by OSSM or Shio to get '
                             'tide information')

    def to_serialize(self, json_='webapi'):
        toserial = super(Tide, self).to_serialize(json_)

        if json_ == 'save':
            toserial['filename'] = self.cy_obj.path_filename

        return toserial
