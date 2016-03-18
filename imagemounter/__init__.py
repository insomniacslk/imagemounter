from __future__ import print_function
from __future__ import unicode_literals

__ALL__ = ['Volume', 'Disk', 'ImageParser', 'Unmounter']
__version__ = '2.0.4'

BLOCK_SIZE = 512
VOLUME_SYSTEM_TYPES = ('detect', 'dos', 'bsd', 'sun', 'mac', 'gpt', 'dbfiller')
FILE_SYSTEM_TYPES = ('ext', 'ufs', 'ntfs', 'hfs', 'hfs+', 'xfs', 'iso', 'udf', 'fat',
                     'vmfs', 'squashfs', 'jffs2', 'cramfs', 'minix',
                     'luks', 'bde', 'lvm',
                     'dos', 'mac', 'bsd', 'sun', 'gpt',
                     'dir', 'unknown')


from imagemounter.parser import ImageParser
from imagemounter.disk import Disk
from imagemounter.volume import Volume
from imagemounter.unmounter import Unmounter
