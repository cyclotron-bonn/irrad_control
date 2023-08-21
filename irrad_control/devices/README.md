# udev rules

To guarantee persistent device paths for your irradiation servers [configuration](./devices_config.yaml)
after reboot, a set of [udev](https://en.wikipedia.org/wiki/Udev) rules should be created in a ``.rules` text file and placed in

```bash
/etc/udev/rules.d/
```

An example of such a file is [irrad_udev.rules](./irrad_udev.rules). To find the required information about your connected devices, type

```bash
sudo lsusb -v | grep 'idVendor\|idProduct\|iProduct\|iSerial'
```

After placing the file, reboot or reload the udev rules and reconnect your devices

```bash
sudo udevadm control --reload
```
