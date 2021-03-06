# coding: utf-8
#

# Copyright (C) 1994-2018 Altair Engineering, Inc.
# For more information, contact Altair at www.altair.com.
#
# This file is part of the PBS Professional ("PBS Pro") software.
#
# Open Source License Information:
#
# PBS Pro is free software. You can redistribute it and/or modify it under the
# terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# PBS Pro is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.
# See the GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Commercial License Information:
#
# For a copy of the commercial license terms and conditions,
# go to: (http://www.pbspro.com/UserArea/agreement.html)
# or contact the Altair Legal Department.
#
# Altair’s dual-license business model allows companies, individuals, and
# organizations to create proprietary derivative works of PBS Pro and
# distribute them - whether embedded or bundled with other software -
# under a commercial license agreement.
#
# Use of Altair’s trademarks, including but not limited to "PBS™",
# "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's
# trademark licensing policies.

import errno
from optparse import OptionParser
import os
import re
import sys
import platform


def reportsockets_win(f):
    temp = f.read().split(',')[0]
    if temp.find('sockets:') != -1:
        return int(temp.replace('sockets:', ''))
    return 0


try:
    import xml.parsers.expat
    from xml.parsers.expat import ExpatError

    def reportsockets(dir, files):
        """
        Look for and report the number of "Socket" elements in a string
        produced by hwloc_topology_export_xmlbuffer().

        This version of reportsockets uses expat to parse the XML.
        If the PBS version of Python does not allow import of expat,
        we go on to try a simpler approach (below).
        """
        def socketXMLstart(name, attrs):
            if name == "BasilResponse":
                socketXMLstart.isCray = True
                return
            if (name == "info" and attrs.get("name") == "hwlocVersion" and
                    re.search(r'1.11.*', attrs.get("value"))):
                socketXMLstart.hwloclatest = 1
                return
            if socketXMLstart.isCray:
                if name == "Node":
                    socketXMLstart.nsockets += 2
            else:
                if (name == "object" and (
                    (socketXMLstart.hwloclatest == 1 and attrs.get("type") ==
                        "Package") or (socketXMLstart.hwloclatest == 0 and
                                       attrs.get("type") == "Socket"))):
                    socketXMLstart.nsockets += 1

        if files is None:
            compute_socket_nodelist = True
            try:
                files = os.listdir(dir)
            except (IOError, OSError), (e, strerror):
                print "%s:  %s (%s)" % (dir, strerror, e)
                return
        else:
            compute_socket_nodelist = False
        try:
            maxwidth = max(map(len, files))
        except StandardError, e:
            print 'max/map failed: %s' % e
            return
        for name in files:
            pathname = os.sep.join((dir, name))
            try:
                socketXMLstart.nsockets = 0
                socketXMLstart.hwloclatest = 0
                with open(pathname, "r") as f:
                    if platform.system() == "Windows":
                        socketXMLstart.nsockets = reportsockets_win(f)
                    else:
                        try:
                            socketXMLstart.isCray = False
                            p = xml.parsers.expat.ParserCreate()
                            p.StartElementHandler = socketXMLstart
                            p.ParseFile(f)
                        except ExpatError, e:
                            print "%s:  parsing error at line %d, column %d" \
                                % (name, e.lineno, e.offset)
                    print "%-*s%d" % (maxwidth + 1, name,
                                      socketXMLstart.nsockets)
            except IOError, (e, strerror):
                if e == errno.ENOENT:
                    if compute_socket_nodelist is False:
                        print "no socket information available for node %s" \
                            % name
                    continue
                else:
                    print "%s:  %s (%s)" % (pathname, strerror, e)
                    raise

except ImportError:
    def reportsockets(dir, files):
        """
        Look for and report the number of "Socket" elements in a string
        produced by hwloc_topology_export_xmlbuffer().

        This is a backup version of reportsockets which we use when an
        import of the xml.parsers.expat module fails.  In this version,
        we simply count occurrences of "Socket" objects.
        """
        socketpattern = r'<\s*object\s+type="Socket"'
        packagepattern = r'<\s*object\s+type="Package"'
        hwloclatestpattern = r'<\s*info\s+name="hwlocVersion"\s+value="1.11.*'
        if files is None:
            compute_socket_nodelist = True
            try:
                files = os.listdir(dir)
            except (IOError, OSError), (e, strerror):
                print "%s:  %s (%s)" % (dir, strerror, e)
                return
        else:
            compute_socket_nodelist = False
        try:
            maxwidth = max(map(len, files))
        except StandardError, e:
            print 'max/map failed: %s' % e
            return
        for name in files:
            pathname = os.sep.join((dir, name))
            try:
                with open(pathname, "r") as f:
                    if platform.system() == "Windows":
                        nsockets = reportsockets_win(f)
                    else:
                        data = f.read()
                        if re.search(hwloclatestpattern, data):
                            hwloclatest = 1
                        if hwloclatest == 1:
                            nsockets = len(re.findall(packagepattern, data))
                        else:
                            nsockets = len(re.findall(socketpattern, data))
                    print "%-*s%d" % (maxwidth + 1, name, nsockets)
            except IOError, (e, strerror):
                if e == errno.ENOENT:
                    if compute_socket_nodelist is False:
                        print "no socket information available for node %s" \
                            % name
                    continue
                else:
                    print "%s:  %s (%s)" % (pathname, strerror, e)
                    raise

if __name__ == "__main__":
    usagestr = "usage:  %prog [ -a -s ]\n\t%prog -s node1 [ node2 ... ]"
    parser = OptionParser(usage=usagestr)
    parser.add_option("-a", "--all", action="store_true", dest="allnodes",
                      help="report on all nodes")
    parser.add_option("-s", "--sockets", action="store_true", dest="sockets",
                      help="report node socket count")
    (options, progargs) = parser.parse_args()

    try:
        topology_dir = os.sep.join((os.environ["PBS_HOME"], "server_priv",
                                    "topology"))
    except KeyError:
        print "PBS_HOME must be present in the caller's environment"
        sys.exit(1)
    if options.allnodes:
        if options.sockets:
            reportsockets(topology_dir, None)
    else:
        if options.sockets:
            reportsockets(topology_dir, progargs)
