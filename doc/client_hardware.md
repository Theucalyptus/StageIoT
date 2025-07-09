# Client Hardware
In our setup, the client is a NVidia Jetson Orin Nano, connectd to a Luxonis OAK-D Camera via USB-C and a LoPy 4 for LoRa connectivity via UART on the GPIO pins of the Jetson. The Jetson itself acts as a WiFi AP for the androind smartphone, a Crosscall Core-Z5, to connect to.


## NVIDIA Jetson Orin Nano
We used a Nvidia Jetson Orin Nano as our embedded computer, but any other device running Linux with WiFi could be used.


### Compiling a custom Linux Kernel :
While developing the platform, we found out that the default linux kernel on the Jetson (as of Jetpack 36.3) came with support for Bluetooth RFCOMM (`CONFIG_BT_RFCOMM`) and USB Tethering (`CONFIG_USB_NET_RNDIS_HOST`) disabled.

USB Tethering is useful to have internet access via a phone connected via USB (as the WiFi could be unavailable if used to communicate with the *sensor phone*, which may not be the same), and Bluetooth RFCOMM support is required for serial bluetooth communication, as Android only support this protocol for Bluetooth sockets (and its generaly easier to work with)

To enable these features, one needs to recompile the linux kernel :
https://docs.nvidia.com/jetson/archives/r36.4.3/DeveloperGuide/SD/Kernel/KernelCustomization.html (This link is specific to a Jetson Linux release and may be outdated, please check up-to-date instructions for your version)

The official guide is/was missing some information :
- The guide recommands to use the `source_sync.sh` script, but doesn't precise where to find it: it is inside the "Driver Package (BSP)", available on the Jetson Linux SDK page https://developer.nvidia.com/embedded/jetson-linux-r3644 (This link will change depending on your version of the OS)

- NVidia says you should use their own toolchain, but in our case the kernel would not compile, with a "unkown compiler" error when trying to use it. We used Ubuntu's provided version of GCC with `CROSS_COMPILE=/usr/bin/aarch64-linux-gnu-` and it worked without issues.

- NVidia says to run the command "make -C kernel" to compile the kernel, however this command builds the kernel with the default configuration and doesn't prompt you to change it. We edited the `Linux_for_Tegra/source/kernel/Makefile` and added a call to menuconfig in the kernel target of the makefile:
```makefile
kernel:
	@echo   "================================================================================"
	@echo   "Building $(KERNEL_SRC_DIR) sources"
	@echo   "================================================================================"
	$(MAKE) \
		ARCH=arm64 \
		-C $(kernel_source_dir) $(O_OPT) \
		LOCALVERSION=$(version) \
		$(KERNEL_DEF_CONFIG)
    
    # WE ADDED THIS
    $(MAKE) \
        ARCH=arm64 \
        -C $(kernel_source_dir) $(O_OPT) \
        LOCALVERSION=$(version) \
        menuconfig

    $(MAKE) \ # ...
```
to edit the configuration with menuconfig before the compilation begins.
After that, we followed the official instructions.

## LoPy 4
We used multiple LoPy 4 as our LoRa transceivers.
We provide two version of the program to be used on the lopy4: `main.py` uses a dedicated UART interface using pins on the Expansion Board, and `main_usb.py` uses the usb cable to communicate.
To upload your programs to the device with the VSCode extension, we found that any firmware with version <=1.19 doesn't work, so make sure to update to version 1.20 or above. 
You may need to allow your user account to access the device, please check [client.md](./client.md) for how to fix uart permission.