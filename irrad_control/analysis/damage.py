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

    # Dict that holds results and error maps; bin centers
    results = {r: None for r in ('proton', 'neq', 'tid')}
    errors = {e: None for e in results}
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

            # Initialize damage and error maps
            if nfile == 0:

                results['proton'], errors['proton'], bin_centers['x'], bin_centers['y'] = fluence.generate_fluence_map(beam_data=data_part[server]['Beam'],
                                                                                                                       scan_data=data_part[server]['Scan'],
                                                                                                                       beam_sigma=beam_sigma,
                                                                                                                       bins=bins)
                # Generate eqivalent fluence map as well as TID map
                results['neq'] = results['proton'] * server_config['daq']['kappa']
                results['tid'] = formulas.tid_scan(proton_fluence=results['proton'], stopping_power=damage_kwargs['stopping_power'])

                continue

            fluence_map_part, fluence_map_part_error, _, _ = fluence.generate_fluence_map(beam_data=data_part[server]['Beam'],
                                                                                          scan_data=data_part[server]['Scan'],
                                                                                          beam_sigma=beam_sigma,
                                                                                          bins=bins)
            # Add to overall map
            results['proton'] += fluence_map_part
            errors['proton'] = (errors['proton']**2 + fluence_map_part_error**2)**.5
            
            # Add to eqivalent fluence map as well as TID map
            results['neq'] += results['proton'] * server_config['daq']['kappa']
            results['tid'] += formulas.tid_scan(proton_fluence=results['proton'], stopping_power=damage_kwargs['stopping_power'])

            # Error calculation
            errors['neq'] = ((server_config['daq']['kappa'] * errors['proton'])**2 + (results['proton'] * 0.6)**2)**0.5  # FIXME: read hardness factor error from config
            errors['tid'] = formulas.tid_scan(proton_fluence=errors['proton'], stopping_power=damage_kwargs['stopping_power'])

    else:

        server = damage_kwargs['server']
                    
        results['proton'], errors['proton'], bin_centers['x'], bin_centers['y'] = fluence.generate_fluence_map(beam_data=data[server]['Beam'],
                                                                                                               scan_data=data[server]['Scan'],
                                                                                                               beam_sigma=beam_sigma,
                                                                                                               bins=bins)
        # Generate eqivalent fluence map as well as TID map
        results['neq'] = results['proton'] * damage_kwargs['hardness_factor']
        print("hardness {}, stoppower {}".format(damage_kwargs['hardness_factor'], damage_kwargs['stopping_power']))
        results['tid'] = formulas.tid_scan(proton_fluence=results['proton'], stopping_power=damage_kwargs['stopping_power'])

        # Error calculation
        errors['neq'] = ((damage_kwargs['hardness_factor'] * errors['proton'])**2 + (results['proton'] * 0.6)**2)**.5  # FIXME: read hardness factor error from config
        errors['tid'] = formulas.tid_scan(proton_fluence=errors['proton'], stopping_power=damage_kwargs['stopping_power'])

    if any(a is None for a in (list(bin_centers.values()) + list(errors.values()) + list(results.values()))):
        raise ValueError('Uninitialized values! Something went wrong - maybe files not found?')

    logging.info("Generating plots ...")

    # Loop over all damage maps
    for damage, map in results.items():
    
        dut_map, dut_centers_x, dut_centers_y = fluence.extract_dut_map(fluence_map=map,
                                                                        map_bin_centers_x=bin_centers['x'],
                                                                        map_bin_centers_y=bin_centers['y'],
                                                                        dut_rectangle=dut_rectangle,  # FIXME: read from irrad data
                                                                        center_symm=True)  # FIXME: read from irrad data

        # Extract respective dut error map
        dut_error_map, _, _ = fluence.extract_dut_map(fluence_map=errors[damage],
                                                      map_bin_centers_x=bin_centers['x'],
                                                      map_bin_centers_y=bin_centers['y'],
                                                      dut_rectangle=dut_rectangle,  # FIXME: read from irrad data
                                                      center_symm=True)  # FIXME: read from irrad data

        for damage_map, centers_x, centers_y in [(map, bin_centers['x'], bin_centers['y']), (dut_map, dut_centers_x, dut_centers_y)]:

            is_dut = damage_map.shape == dut_map.shape                

            fig, _ = plotting.plot_damage_map_3d(damage_map=damage_map, map_centers_x=centers_x, map_centers_y=centers_y, contour=not is_dut, damage=damage, server=server, dut=is_dut)
            figs.append(fig)

            fig, _ = plotting.plot_damage_error_3d(damage_map=damage_map, error_map=errors[damage] if not is_dut else dut_error_map, map_centers_x=centers_x, map_centers_y=centers_y, contour=not is_dut, damage=damage, server=server, dut=is_dut)
            figs.append(fig)

            fig, _ = plotting.plot_damage_map_2d(damage_map=damage_map, map_centers_x=centers_x, map_centers_y=centers_y, damage=damage, server=server, dut=is_dut)
            figs.append(fig)

            fig, _ = plotting.plot_damage_map_contourf(damage_map=damage_map, map_centers_x=centers_x, map_centers_y=centers_y, damage=damage, server=server, dut=is_dut)
            figs.append(fig)

    logging.info("Finished plotting.")

    return figs