from __future__ import absolute_import
from __future__ import print_function
import os
from mojo.extensions import ExtensionBundle


basePath = os.path.dirname(__file__)
extensionPath = os.path.join(basePath, "BezierSurgeon.roboFontExt")
libPath = os.path.join(basePath, "lib")
# htmlPath = os.path.join(basePath, "html")

B = ExtensionBundle()

B.name = "Bezier Surgeon"
B.version = "2.002"
B.developer = "Connor Davenport"
B.developerURL = 'http://www.connordavenport.com/'
B.mainScript = "BezierSurgeon.py"
B.launchAtStartUp = True
B.addToMenu = [
    {
        'path' : 'BezierSurgeon.py',
        'preferredName': 'Bezier Surgeon',
        'shortKey' : '',
    }]
    
B.requiresVersionMajor = '4'
B.requiresVersionMinor = '1'
# B.infoDictionary["html"] = True

B.save(extensionPath, libPath=libPath,  pycOnly=False)
# htmlPath=htmlPath,
print("Done")