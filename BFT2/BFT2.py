#!/usr/bin/env python

import sys
import os
import time
import dialog
import robot
import helpers

colorize= { 
# black, red, green, yellow, blue, magenta, cyan white \Z0-\Z9
        'OK': "\Z2\ZbOK\Zn",
        'FAIL': "\Z1\ZbFAIL\Zn",
        'Error': "\Z1\ZbError\Zn",
        'ERROR': "\Z1\ZBERROR\Zn",
        'PASS': "\Z2\ZbPASS\Zn",
        }

class BFT2UI(helpers.CmdRunner):
    '''
    Simple UI for BFT2 collections of test cases. Uses on dialog/xdialog
    '''
    def __init__(self, logfile="dscheduler.log", suit_path="quickstart"):
        self.logfile = open(logfile, 'w')
        sys.stderr = self.logfile
        self.suit_path = suit_path
        self.dlg = dialog.Dialog(dialog="dialog")
        self.flush_state()
        self.chosen_tags = []
        self.dlg.setBackgroundTitle(self.backtitle)
        self.display()

    def _find_usb_drive(self):
        _attempts = 3
        while not self._output and _attempts:
            self.run('ls /dev/disk/by-id | grep "usb.*part1"')
            if self._error:
                return "ERROR: %s" % self._error
            if not self._output:
                _attempts -= 1
                self.dlg.msgbox("Please insert the USB drive then press OK")
        if not _attempts:
            return "ERROR: couldn't find any USB drives"
        return self._output

    def _get_text_height(self):
        return len(self.text.split('\n')) + 5
    def _set(self, x):
        raise Exception("Property is readonly!")
    height = property(_get_text_height, _set)

    def get_text_width(self):
        return max(map(len, self.text.split('\n'))) + 5
    width = property(get_text_width, _set)

    def __str__(self):
        return str([(attr, getattr(self, attr)) for attr in self.__dict__])

    def _reports_to_usb_drive(self, devID):
        _mount_path = "/mnt/%s" % devID + str(time.time())
        _device = "/dev/disk/by-id/%s" % devID
        try:
            os.mkdir(_mount_path)
            self.run("mount %s %s" % (_device, _mount_path), do_raise=True)
            self.text_update(str(_out))
            self.dlg.infobox(self.text, self.height, self.width)
            _dest_path = _mount_path + "/bft2report_%s" % time.strftime("%Y_%m_%d-%H-%M-%s")
            os.mkdir(_dest_path)
            self.run("cp *.html %(path)s; cp *.xml %(path)s; cp *.log %(path)s" % {'path':_dest_path}, do_raise=True)
            self.run("umount %s" % _mount_path, do_raise=True)
            os.rmdir(_mount_path)
        except Exception, e:
            return "ERROR: %s" % e
        return 'OK'

    def flush_state(self):
        self.suit = None
        self.text = ""
        self.state = "restart"
        self.title = str(self.__class__).split('.')[1]
        self.backtitle = self.title
        self.dlg.DIALOGRC = ''

    def log(self, *args):
        self.logfile.write(str(time.ctime()) + ': ' + str(args) + '\n')

    def quit(self):
        self.text_update(" Bye! ")
        self.log("quit", self)
        self.logfile.close()
        exit(0)

    def text_update(self, info, widget="infobox", clear=False):
        if clear:
            self.text = ""
        for token in colorize:
            info = info.replace(token, colorize[token])
        self.text += "\n" + info
        if self.state != "restart":
            self.dlg.DIALOGRC = os.path.abspath(".dialogrc.%s" % self.state)

    def draw_menu(self):
        height = len(self.text[1]) + 7
        width = max(max(max(map(lambda x: len(x[1]), self.text[1])), len(self.text[0])), len(self.title)) + 5
        return self.dlg.menu(text=self.text[0], height=height, width=width, menu_height=7, choices=self.text[1])

    def display(self):
        while self.state != "exit":
            if self.state == "restart":
                self.do()
        self.dlg.msgbox(self.text, self.height, self.width, "Bye!")
        self.quit()

    def load_test_suit(self):
        if os.path.isdir(self.suit_path):
            return #TODO
        if not os.path.isfile(self.suit_path):
            self.text_update("[FAIL] Could not load test suit")
            return
        # reading test suite file
        try:
            self.suit = robot.parsing.TestData(source=self.suit_path)
            self.tags = set([])
            self.log(self.tags)
            for testcase in self.suit.testcase_table:
                if testcase.tags.value.__class__ == list:
                    self.tags.update(map(str,testcase.tags.value))
                else:
                    self.tags.add(str(testcase.tags.value))
        except Exception, e:
            self.log(e)
            self.title = colorize["Error"]
            self.text_update("[FAIL] %s is not a valid test suit file" % self.suit_path, widget="msgbox")
            return
        self.text_update("[OK] Test suit %s" % self.suit)

    def check_pybot(self):
        # checking pybot executable
        try:
            self.pybot = dialog._path_to_executable("pybot")
        except Exception:
            self.title = colorize["Error"]
            self.text_update("[FAIL] Could not found pybot executable")
            return
        self.text_update("[OK] pybot executable")

    def do(self):
        self.check_pybot()
        self.load_test_suit()
        if not self.suit or not self.pybot:
            self.state = "exit"
            return
        if self.tags:
            self.chosen_tags = self.dlg.checklist(text="Please, choose tests:", choices=[(str(x[1]), str(x[0]), 'off') for x in zip(range(len(self.tags) + 1), self.tags)])[1]
        if not self.chosen_tags:
            self.chosen_tags = self.tags
        self.text_update("[OK] Tags to run: %s" % self.chosen_tags)
        exit = self.dlg.yesno(self.text + "\nProceed?\n", len(self.text.split('\n')) + 5, max(map(len, self.text.split('\n'))) + 5, "Run", "Exit")
        if exit:
            self.state = "exit"
            return
        self.log(' '.join(map(str, self.chosen_tags)))
        self.text_update("", clear=True)
        _cmd = [self.pybot, "--include"]
        _cmd.extend(self.chosen_tags)
        _cmd.append(self.suit_path)
        self.log(_cmd)
        self.run(_cmd, shell=False, pipe=False)
        # TODO read report, show results
        exit = self.dlg.yesno(self.text, self.height, self.width, "Run again", "Write to USB and exit")
        if exit:
            self.state = "exit"
            _usb = self._find_usb_drive()
            self.log(_usb)
            if not _usb or 'ERROR' in _usb:
                self.dlg.msgbox(_usb and "%s" % _usb or "Cannot write reports")
            else:
                self.text_update("Writing reports to USB-drive.. ", clear=True)
                self.dlg.infobox(self.text, self.height, self.width)
                self.text_update(self._reports_to_usb_drive(_usb))
                self.dlg.infobox(self.text, self.height, self.width)
        else:
            self.flush_state()

def main():
    if len(sys.argv) > 1:
        print sys.argv
        scheduler = BFT2UI(suit_path=sys.argv[1])

if __name__ == "__main__":
    main()