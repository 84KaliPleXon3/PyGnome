'''
model dispersion process
'''
from __future__ import division

import copy

import numpy as np

import gnome    # required by deserialize

from gnome import constants
from gnome.cy_gnome.cy_weatherers import disperse_oil
from gnome.array_types import (viscosity,
                               mass,
                               density,
                               fay_area,
                               frac_water,
                               droplet_avg_size)

from gnome.utilities.serializable import Serializable, Field

from .core import WeathererSchema
from gnome.weatherers import Weatherer

g = constants.gravity  # the gravitational constant.


class NaturalDispersion(Weatherer, Serializable):
    _state = copy.deepcopy(Weatherer._state)
    _state += [Field('water', save=True, update=True, save_reference=True),
               Field('waves', save=True, update=True, save_reference=True)]
    _schema = WeathererSchema

    def __init__(self,
                 waves=None,
                 water=None,
                 **kwargs):
        '''
        :param conditions: gnome.environment.Conditions object which contains
            things like water temperature
        :param waves: waves object for obtaining wave_height, etc at given time
        '''
        self.waves = waves
        self.water = water

        super(NaturalDispersion, self).__init__(**kwargs)
        self.array_types.update({'viscosity': viscosity,
                                 'mass':  mass,
                                 'density': density,
                                 'fay_area': fay_area,
                                 'frac_water': frac_water,
                                 'droplet_avg_size': droplet_avg_size,
                                 })

    def prepare_for_model_run(self, sc):
        '''
        add dispersion and sedimentation keys to mass_balance
        Assumes all spills have the same type of oil
        '''
        # create 'natural_dispersion' and 'sedimentation keys
        # if they doesn't exist
        # let's only define this the first time
        if self.on:
            super(NaturalDispersion, self).prepare_for_model_run(sc)
            sc.mass_balance['natural_dispersion'] = 0.0
            sc.mass_balance['sedimentation'] = 0.0

    def prepare_for_model_step(self, sc, time_step, model_time):
        '''
        Set/update arrays used by dispersion module for this timestep:

        '''
        super(NaturalDispersion, self).prepare_for_model_step(sc,
                                                              time_step,
                                                              model_time)

        if not self.active:
            return

    def weather_elements(self, sc, time_step, model_time):
        '''
        weather elements over time_step
        - sets 'natural_dispersion' and 'sedimentation' in sc.mass_balance
        '''
        if not self.active:
            return

        if sc.num_released == 0:
            return

        # from the waves module
        wave_height = self.waves.get_value(model_time)[0]
        frac_breaking_waves = self.waves.get_value(model_time)[2]
        disp_wave_energy = self.waves.get_value(model_time)[3]

        visc_w = self.waves.water.kinematic_viscosity
        rho_w = self.waves.water.density

        # web has different units
        sediment = self.waves.water.get('sediment', unit='kg/m^3')

        for substance, data in sc.itersubstancedata(self.array_types):
            if len(data['mass']) == 0:
                # substance does not contain any surface_weathering LEs
                continue

            V_entrain = constants.volume_entrained
            ka = constants.ka  # oil sticking term

            disp = np.zeros((len(data['mass'])), dtype=np.float64)
            sed = np.zeros((len(data['mass'])), dtype=np.float64)
            droplet_avg_size = data['droplet_avg_size']

            #print 'dispersion: mass_components = ', data['mass_components'].sum(1)

            disperse_oil(time_step,
                         data['frac_water'],
                         data['mass'],
                         data['viscosity'],
                         data['density'],
                         data['fay_area'],
                         disp,
                         sed,
                         droplet_avg_size,
                         frac_breaking_waves,
                         disp_wave_energy,
                         wave_height,
                         visc_w,
                         rho_w,
                         sediment,
                         V_entrain,
                         ka)

            sc.mass_balance['natural_dispersion'] += np.sum(disp[:])

            if data['mass'].sum() > 0:
                disp_mass_frac = np.sum(disp[:]) / data['mass'].sum()
                if disp_mass_frac > 1:
                    disp_mass_frac = 1
            else:
                disp_mass_frac = 0

            data['mass_components'] = ((1 - disp_mass_frac) *
                                       data['mass_components'])
            data['mass'] = data['mass_components'].sum(1)

            sc.mass_balance['sedimentation'] += np.sum(sed[:])

            if data['mass'].sum() > 0:
                sed_mass_frac = np.sum(sed[:]) / data['mass'].sum()
                if sed_mass_frac > 1:
                    sed_mass_frac = 1
            else:
                sed_mass_frac = 0

            data['mass_components'] = ((1 - sed_mass_frac) *
                                       data['mass_components'])
            data['mass'] = data['mass_components'].sum(1)

            self.logger.debug('{0} Amount Dispersed for {1}: {2}'
                              .format(self._pid,
                                      substance.name,
                                      sc.mass_balance['natural_dispersion']))
            #print 'dispersion: mass_components = ', data['mass_components'].sum(1)

        sc.update_from_fatedataview()

    def disperse_oil(self, time_step,
                     frac_water,
                     mass,
                     viscosity,
                     density,
                     fay_area,
                     disp_out,
                     sed_out,
                     frac_breaking_waves,
                     disp_wave_energy,
                     wave_height,
                     visc_w,
                     rho_w,
                     sediment,
                     V_entrain,
                     ka):
        '''
            Right now we just want to recreate what the lib_gnome dispersion
            function is doing...but in python.
            This will allow us to more easily refactor, and we can always
            then put it back into lib_gnome if necessary.
            (TODO: Not quite finished with the function yet.)
        '''
        D_e = disp_wave_energy
        f_bw = frac_breaking_waves
        H_rms = wave_height

        # dispersion term at current time.
        C_disp = D_e ** 0.57 * f_bw

        for i, (rho, mass, visc, Y, A) in enumerate(zip(density, mass,
                                                        viscosity, frac_water,
                                                        fay_area)):
            pass

    def serialize(self, json_='webapi'):
        """
        'water'/'waves' property is saved as references in save file
        """
        toserial = self.to_serialize(json_)
        schema = self.__class__._schema()
        serial = schema.serialize(toserial)

        if json_ == 'webapi':
            if self.waves:
                serial['waves'] = self.waves.serialize(json_)
            if self.water:
                serial['water'] = self.water.serialize(json_)

        return serial

    @classmethod
    def deserialize(cls, json_):
        """
        Append correct schema for water / waves
        """
        if not cls.is_sparse(json_):
            schema = cls._schema()
            dict_ = schema.deserialize(json_)

            if 'water' in json_:
                obj = json_['water']['obj_type']
                dict_['water'] = (eval(obj).deserialize(json_['water']))

            if 'waves' in json_:
                obj = json_['waves']['obj_type']
                dict_['waves'] = (eval(obj).deserialize(json_['waves']))

            return dict_
        else:
            return json_
