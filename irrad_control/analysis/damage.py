import logging
from types import GeneratorType

from irrad_control.analysis import plotting
from irrad_control.analysis import fluence
from irrad_control.analysis import formulas


def analyse_radiation_damage(data, **damage_kwargs):

    figs = []

    beam_sigma = (2*2.01, 2*1.37)  # mm FIXME: get value from measurement outside vacuum; this value corresponds to 'visual' + measurement in vacuum
    dut_rectangle = (25, 25)  # mm FIXME: get from *IRRAD* data
    bins = (100, 100)

    # Dict that holds fluence and TID maps
    damage_maps = {'neq': None, 'tid': None, 'fluence': None}
    bin_centers = {'x': None, 'y': None}

    # We have a multipart irradiation with mulitple datafiles
    if isinstance(data, GeneratorType):
        
        server = None  # Only allow files with exactly one server for multipart to avoid adding unrelated fluence maps

        # Loop over generator and get partial data files
        for nfile, data_part, config_part, session_basename in data:

            logging.info(f"Generating multipart damage distributions from file {session_basename} (file number {nfile+1})")

            if len(config_part['server']) != 1:
                raise ValueError(f"Multipart damage analysis only supports input files containing data from 1 server; found {len(len(config_part['server']))}")
            
            server_config, = config_part['server'].values()

            # Only allow one fixed server for multipart
            if server is None:
                server = server_config['name']

            if server not in data_part:
                raise KeyError(f"Server '{server}' not present in file {session_basename}!")

            # Initialize fluence and TID maps
            if damage_maps['fluence'] is None:

                damage_maps['fluence'], bin_centers['x'], bin_centers['y'] = fluence.generate_fluence_map(beam_data=data_part[server]['Beam'],
                                                                                                          scan_data=data_part[server]['Scan'],
                                                                                                          beam_sigma=beam_sigma,
                                                                                                          bins=bins)
                # Generate TID map from potentially different stopping power irradiation
                damage_maps['tid'] = formulas.tid_scan(proton_fluence=damage_maps['fluence'], stopping_power=damage_kwargs['stopping_power'])

                # Generate NEQ fluence map from potentially different hardness_factor
                damage_maps['neq'] = damage_maps['fluence'] * server_config['daq']['kappa']

            # Sum up damage maps from different files
            else:

                fluence_map_part, _, _ = fluence.generate_fluence_map(beam_data=data_part[server]['Beam'],
                                                                      scan_data=data_part[server]['Scan'],
                                                                      beam_sigma=beam_sigma,
                                                                      bins=bins)
                # Add to overall map
                damage_maps['fluence'] += fluence_map_part
                damage_maps['tid'] += formulas.tid_scan(proton_fluence=fluence_map_part, stopping_power=damage_kwargs['stopping_power'])
                damage_maps['neq'] += fluence_map_part * server_config['daq']['kappa']

    else:

        server = damage_kwargs['server']
                    
        damage_maps['fluence'], bin_centers['x'], bin_centers['y'] = fluence.generate_fluence_map(beam_data=data[server]['Beam'],
                                                                                                  scan_data=data[server]['Scan'],
                                                                                                  beam_sigma=beam_sigma,
                                                                                                  bins=bins)

        # Generate TID map from potentially different stopping power irradiation
        damage_maps['tid'] = formulas.tid_scan(proton_fluence=damage_maps['fluence'], stopping_power=damage_kwargs['stopping_power'])

        # Generate NEQ fluence map from potentially different hardness_factor
        damage_maps['neq'] = damage_maps['fluence'] * damage_kwargs['hardness_factor']


    # Loop over all damage maps
    for damage, map in damage_maps.items():    
    
        dut_map, dut_centers_x, dut_centers_y = fluence.extract_dut_map(fluence_map=map,
                                                                        map_bin_centers_x=bin_centers['x'],
                                                                        map_bin_centers_y=bin_centers['y'],
                                                                        dut_rectangle=dut_rectangle,
                                                                        center_symm=True)

        for damage_map, centers_x, centers_y in [(map, bin_centers['x'], bin_centers['y']), (dut_map, dut_centers_x, dut_centers_y)]:

            is_dut = damage_map.shape == dut_map.shape                  

            fig, _ = plotting.plot_damage_map_3d(damage_map=damage_map, map_centers_x=centers_x, map_centers_y=centers_y, contour=not is_dut, damage=damage, server=server, dut=is_dut)
            figs.append(fig)

            fig, _ = plotting.plot_damage_map_2d(damage_map=damage_map, map_centers_x=centers_x, map_centers_y=centers_y, damage=damage, server=server, dut=is_dut)
            figs.append(fig)

            fig, _ = plotting.plot_damage_map_contourf(damage_map=damage_map, map_centers_x=centers_x, map_centers_y=centers_y, damage=damage, server=server, dut=is_dut)
            figs.append(fig)

    return figs