KDIR ?= /lib/modules/`uname -r`/build

default:
	$(MAKE) -C $(KDIR) M=$$PWD/wlags49_h2
	$(MAKE) -C $(KDIR) M=$$PWD/wlags49_h25

install:
	$(MAKE) -C $(KDIR) M=$$PWD/wlags49_h2 modules_install
	$(MAKE) -C $(KDIR) M=$$PWD/wlags49_h25 modules_install
	depmod

clean:
	find \( -name '*.d' -or -name '*.o' -or -name '*.ko' \
		-or -name '*.mod*' -or -name '*.cmd' \) -delete
