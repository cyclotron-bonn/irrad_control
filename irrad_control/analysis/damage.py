from irrad_control.analysis import plotting
from irrad_control.analysis import fluence
from irrad_control.analysis import formulas


def analyse_radiation_damage(data, server, hardness_factor, stopping_power):

    figs = []

    beam_sigma = (2.01, 1.37)  # mm FIXME: get value from measurement outside vacuum; this value corresponds to 'visual' + measurement in vacuum
    dut_rectangle = (25, 17.5)  # mm FIXME: get from *IRRAD* data

    fluence_map, map_centers_x, map_centers_y = fluence.generate_fluence_map(beam_data=data[server]['Beam'],
                                                                                            scan_data=data[server]['Scan'],
                                                                                            beam_sigma=beam_sigma,
                                                                                            bins=(100, 100))
    
    dut_map, dut_centers_x, dut_centers_y = fluence.extract_dut_map(fluence_map=fluence_map,
                                                                                map_bin_centers_x=map_centers_x,
                                                                                map_bin_centers_y=map_centers_y,
                                                                                dut_rectangle=dut_rectangle,
                                                                                center_symm=True)

    for map, centers_x, centers_y in [(fluence_map, map_centers_x, map_centers_y), (dut_map, dut_centers_x, dut_centers_y)]:

        for damage, damage_map in [('NIEL', map * hardness_factor), ('TID', formulas.tid_scan(map, stopping_power=stopping_power))]:

            # Whether we are looking at the DUT
            is_dut = damage_map.shape == dut_map.shape
            
            fig, _ = plotting.plot_damage_map_3d(damage_map=damage_map, map_centers_x=centers_x, map_centers_y=centers_y, contour=not is_dut, damage=damage, server=server, dut=is_dut)
            figs.append(fig)

            fig, _ = plotting.plot_damage_map_2d(damage_map=damage_map, map_centers_x=centers_x, map_centers_y=centers_y, damage=damage, server=server, dut=is_dut)
            figs.append(fig)

            fig, _ = plotting.plot_damage_map_contourf(damage_map=damage_map, map_centers_x=centers_x, map_centers_y=centers_y, damage=damage, server=server, dut=is_dut)
            figs.append(fig)

    return figs