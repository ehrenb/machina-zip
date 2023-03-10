import base64
import json
import os
import tempfile
from zipfile import ZipFile

from machina.core.worker import Worker

class ZipAnalyzer(Worker):
    types = ["zip"]
    next_queues = ['Identifier']


    def __init__(self, *args, **kwargs):
        super(ZipAnalyzer, self).__init__(*args, **kwargs)

    def callback(self, data, properties):
        data = json.loads(data)

        # resolve path
        target = self.get_binary_path(data['ts'], data['hashes']['md5'])
        self.logger.info(f"resolved path: {target}")
        self.logger.debug("test debug log")
        zf = ZipFile(target)
        namelist = zf.namelist()

        origin = {
            "ts": data['ts'],
            "md5": data['hashes']['md5'],
            "uid": data['uid'], #I think this is the only field needed, we can grab the unique node based on id alone
            "type": data['type']
        }

        # Retype as APK
        if 'classes.dex' in namelist and 'META-INF/MANIFEST.MF' in namelist:
            # retype (Submit original data to Identifier with origin metadata and 
            # new  type)
            self.logger.info(f"retyping {target} to apk")

            with open(target, 'rb') as f:
                data_encoded = base64.b64encode(f.read()).decode()

            body = {
                "data": data_encoded,
                "origin": origin,
                'type': 'apk'
            }
            self.publish_next(json.dumps(body))


        # Unzip and send each file to the Identifier
        else:
            for name in namelist:
                try:
                    with tempfile.TemporaryDirectory() as tmpdir:
                        filepath = zf.extract(name, tmpdir)
                        if os.path.isfile(filepath):

                            # send the file back to the Identifier
                            with open(filepath, 'rb') as f:
                                data_encoded = base64.b64encode(f.read()).decode()

                            body = {
                                "data": data_encoded,
                                "origin": origin
                            }
                            self.logger.info(f"submitting unzipped: {filepath}")
                            self.publish_next(json.dumps(body))

                except RuntimeError:
                    for password in self.config['worker']['passwords']:
                        try:
                            with tempfile.TemporaryDirectory() as tmpdir:
                                filepath = zf.extract(name, tmpdir, pwd=password)

                                if os.path.isfile(filepath):
                                    with open(filepath, 'rb') as f:
                                        data_encoded = base64.b64encode(f.read()).decode()

                                    body = {
                                        "data": data_encoded,
                                        "origin": origin
                                    }
                                    self.logger.info(f"submitting unzipped: {filepath}")
                                    self.publish_next(json.dumps(body))

                        except RuntimeError:
                            self.logger.warn(f"could not unzip {name} with password {password}")
                            pass
