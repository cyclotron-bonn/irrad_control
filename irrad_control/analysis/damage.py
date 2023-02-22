import logging
from irrad_control.analysis import plotting, fluence, formulas


def main(data, config=None):

    figs = []
    bins = (100, 100)

    # Dict that holds results and error maps; bin centers
    results = {r: None for r in ('primary', 'neq', 'tid')}
    errors = {e: None for e in results}
    bin_centers = {'x': None, 'y': None}

    # We have a multipart irradiation with mulitple datafiles
    if config is None:
        
        server = None  # Only allow files with exactly one server for multipart to avoid adding unrelated fluence maps
        ion_name = None

        # Loop over generator and get partial data files
        for nfile, data_part, config_part, session_basename in data:

            logging.info(f"Generating multipart damage distributions from file {session_basename} (file number {nfile+1})")

            if len(config_part['server']) != 1:
                raise ValueError(f"Multipart damage analysis only supports input files containing data from 1 server; found {len(len(config_part['server']))}")
            
            server_config, = config_part['server'].values()
            
            # Only allow one fixed server for multipart
            if server is None:
                server = server_config['name']
                ion_name = server_config['daq']['ion']
                irrad_data=data_part[server]['Irrad']

            if server not in data_part:
                raise KeyError(f"Server '{server}' not present in file {session_basename}!")

            # Initialize damage and error maps
            if nfile == 0:

                results['primary'], errors['primary'], bin_centers['x'], bin_centers['y'] = fluence.generate_fluence_map(beam_data=data_part[server]['Beam'],
                                                                                                                       scan_data=data_part[server]['Scan'],
                                                                                                                       irrad_data=data_part[server]['Irrad'],
                                                                                                                       bins=bins)
                # Generate eqivalent fluence map as well as TID map
                if server_config['daq']['kappa'] is None:
                    del results['neq']
                else:
                    results['neq'] = results['primary'] * server_config['daq']['kappa']['nominal']
                
                if server_config['daq']['stopping_power'] is None:
                    del results['tid']
                else:
                    results['tid'] = formulas.tid_per_scan(primary_fluence=results['primary'], stopping_power=server_config['daq']['stopping_power'])

                continue

            fluence_map_part, fluence_map_part_error, _, _ = fluence.generate_fluence_map(beam_data=data_part[server]['Beam'],
                                                                                          scan_data=data_part[server]['Scan'],
                                                                                          irrad_data=data_part[server]['Irrad'],
                                                                                          bins=bins)
            # Add to overall map
            results['primary'] += fluence_map_part
            errors['primary'] = (errors['primary']**2 + fluence_map_part_error**2)**.5
            
            # Add to eqivalent fluence map
            if 'neq' in results:
                results['neq'] += results['primary'] * server_config['daq']['kappa']['nominal']
                errors['neq'] = ((server_config['daq']['kappa']['nominal'] * errors['primary'])**2 + (results['primary'] * server_config['daq']['kappa']['sigma'])**2)**0.5
            
            if 'tid' in results:
                results['tid'] += formulas.tid_per_scan(primary_fluence=results['primary'], stopping_power=server_config['daq']['stopping_power'])
                errors['tid'] = formulas.tid_per_scan(primary_fluence=errors['primary'], stopping_power=server_config['daq']['stopping_power'])

    else:

        server = config['name']
        ion_name = config['daq']['ion']
        irrad_data=data[server]['Irrad']
                    
        results['primary'], errors['primary'], bin_centers['x'], bin_centers['y'] = fluence.generate_fluence_map(beam_data=data[server]['Beam'],
                                                                                                               scan_data=data[server]['Scan'],
                                                                                                               irrad_data=irrad_data,
                                                                                                               bins=bins)
        # Generate eqivalent fluence map as well as TID map
        if config['daq']['kappa'] is None:
            del results['neq']
        else:
            results['neq'] = results['primary'] * config['daq']['kappa']['nominal']
            errors['neq'] = ((config['daq']['kappa']['nominal'] * errors['primary'])**2 + (results['primary'] * config['daq']['kappa']['sigma'])**2)**.5
        
        if config['daq']['stopping_power'] is None:
            del results['tid']
        else:
            results['tid'] = formulas.tid_per_scan(primary_fluence=results['primary'], stopping_power=config['daq']['stopping_power'])
            errors['tid'] = formulas.tid_per_scan(primary_fluence=errors['primary'], stopping_power=config['daq']['stopping_power'])

    if any(a is None for a in (list(bin_centers.values()) + list(results.values()))):
        raise ValueError('Uninitialized values! Something went wrong - maybe files not found?')

    logging.info("Generating plots ...")

    # Loop over all damage maps
    for damage, map in results.items():
    
        dut_map, dut_centers_x, dut_centers_y = fluence.extract_dut_map(fluence_map=map,
                                                                        map_bin_centers_x=bin_centers['x'],
                                                                        map_bin_centers_y=bin_centers['y'],
                                                                        irrad_data=irrad_data)

        # Extract respective dut error map
        dut_error_map, _, _ = fluence.extract_dut_map(fluence_map=errors[damage],
                                                      map_bin_centers_x=bin_centers['x'],
                                                      map_bin_centers_y=bin_centers['y'],
                                                      irrad_data=irrad_data)

        for damage_map, centers_x, centers_y in [(map, bin_centers['x'], bin_centers['y']), (dut_map, dut_centers_x, dut_centers_y)]:

            is_dut = damage_map.shape == dut_map.shape                

            fig, _ = plotting.plot_damage_map_3d(damage_map=damage_map, map_centers_x=centers_x, map_centers_y=centers_y, contour=not is_dut, damage=damage, ion_name=ion_name, server=server, dut=is_dut)
            figs.append(fig)

            fig, _ = plotting.plot_damage_error_3d(damage_map=damage_map, error_map=errors[damage] if not is_dut else dut_error_map, map_centers_x=centers_x, map_centers_y=centers_y, contour=not is_dut, damage=damage, ion_name=ion_name,  server=server, dut=is_dut)
            figs.append(fig)

            fig, _ = plotting.plot_damage_map_2d(damage_map=damage_map, map_centers_x=centers_x, map_centers_y=centers_y, damage=damage, ion_name=ion_name, server=server, dut=is_dut)
            figs.append(fig)

            fig, _ = plotting.plot_damage_map_contourf(damage_map=damage_map, map_centers_x=centers_x, map_centers_y=centers_y, damage=damage, ion_name=ion_name, server=server, dut=is_dut)
            figs.append(fig)

    logging.info("Finished plotting.")

    return figs
