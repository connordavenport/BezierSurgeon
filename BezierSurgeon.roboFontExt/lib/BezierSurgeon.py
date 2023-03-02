import AppKit
from defcon import Contour, Font
from defconAppKit.windows.baseWindow import BaseWindowController
from fontParts.fontshell import RBPoint
from fontTools.misc import bezierTools as bT
from lib.tools.notifications import PostNotification
from merz.tools.drawingTools import NSImageDrawingTools
import math
import merz
from mojo.UI import PostBannerNotification, getDefault, setDefault, CurrentGlyphWindow, UpdateCurrentGlyphView, getGlyphViewDisplaySettings, setGlyphViewDisplaySettings, preferencesChanged
from mojo.events import addObserver, removeObserver, EditingTool, installTool, BaseEventTool
from mojo.subscriber import Subscriber, WindowController, registerCurrentGlyphSubscriber
from vanilla import HUDFloatingWindow, Slider, SquareButton,Group


'''
to do:
- fix handle drawing
- add support for quadratic curves
'''


'''
How to use:

BezierSurgeon is a tool to insert points along [cubic] curves at a 
specified angle and/or ratio. To use it, select the tool from the toolbar
at the top of the glyphView. Select a curve and hold down ⇧ shift key and drag
around the width of the contour to control the point position. BS has three functions
for point insertion, CurrentGlyph only - "C", AllFonts at specified Ratio - "R", and AllFonts at
what ever is possible - "A". The latter checks if it is possible to insert the point at the same
angle in all compatible fonts but if not it will attempt to insert it at the ratio.

'''


toolbarIcon = AppKit.NSImage.alloc().initByReferencingFile_("SurgeonIcon.pdf")
toolbarIcon.setTemplate_(True)


class BezierSurgeon(EditingTool):

    debug = True

    def setup(self):
                
        self.selectionColor = None
        self.offCurvesViz = None
        self.glyph = None
        self.selectedContourIndex = None
        self.selectedSegmentIndex = None
        self.segmentPoints = []
        self.percent = 0.5
        self.point = None
        self.duration = .8
        self.upmScale = None
        if AppKit.NSApp().appearance() == AppKit.NSAppearance.appearanceNamed_(AppKit.NSAppearanceNameDarkAqua):
            self.mode = "dark"
            self.suffix = ".dark"
        else:
            self.mode = "light"
            self.suffix = ""
            
        self.onCurveSize = getDefault("glyphViewOncurvePointsSize") * 2.2
        self.offCurveSize = getDefault("glyphViewOncurvePointsSize") * 2
        self.onCurveFill = self.getModeColor("glyphViewCurvePointsFill",self.suffix)
        self.onCurveStroke = self.getModeColor("glyphViewSmoothPointStroke",self.suffix)
        self.offCurveFill = self.getModeColor("glyphViewOffCurvePointsFill",self.suffix)
        self.offCurveStroke = self.getModeColor("glyphViewOffCurveCubicPointsStroke",self.suffix)
        self.handleStroke = list(self.getModeColor("glyphViewHandlesStrokeColor",self.suffix))
        self.handleStroke[3] = .8
        self.handleStroke = tuple(self.handleStroke)
        self.handleWidth = getDefault("glyphViewHandlesStrokeWidth") * .4
        self.strokeWidth = getDefault("glyphViewStrokeWidth")
            
        foregroundLayer = self.extensionContainer(
            identifier="com.roboFont.BezierSurgeon.foreground",
            location='foreground',
            clear=True
        )
        
        backgroundLayer = self.extensionContainer(
            identifier="com.roboFont.BezierSurgeon.foreground",
            location='background',
            clear=True
        )
        
        self.captionTextLayer = foregroundLayer.appendTextLineSublayer(
           backgroundColor=None,
           text="",
           fillColor=(1, 1, 1, 1),
           horizontalAlignment="center"
        )

        self.scaleLayer = foregroundLayer.appendPathSublayer(
            fillColor=None,
            strokeColor=None
        )
        
        self.handleLayer = backgroundLayer.appendPathSublayer(
            fillColor=None,
            strokeColor=None
        )
        
        self.ovalCurveLayer = foregroundLayer.appendPathSublayer(
            fillColor=None,
            strokeColor=None
        )

        self.pointInsertionLayer = foregroundLayer.appendBaseSublayer()
        
        self.addObservers()

        # self.handleLayer.setVisible(True)
        # self.captionTextLayer.setVisible(True)


    # def destroy(self):
    #     self.container.clearSublayers()
        
# ---------------------------------        
# ---------------------------------        


    def addObservers(self):
        self.drawPoints()
        self.offCurvesViz = getGlyphViewDisplaySettings()['OffCurvePoints']
        self.selectionColor = self.getModeColor("glyphViewSelectionColor",self.suffix)
        #self.selectionColor = tuple([i for i in getDefault(f"glyphViewSelectionColor{self.suffix}")])
        setDefault(f"glyphViewSelectionColor{self.suffix}", (0,0,0,0), validate=True)
        preferencesChanged()
        preferencesChanged()
        # for some reason I need to post it twice to trigger a current selection's color
        setGlyphViewDisplaySettings({'OffCurvePoints':False})
        #UpdateCurrentGlyphView()
        
    def removeObservers(self):
        if self.selectionColor:
            selectionColor = self.selectionColor
        else:
            selectionColor = (1,0,0,1)
        setDefault(f"glyphViewSelectionColor{self.suffix}", selectionColor, validate=True)
        preferencesChanged()
        preferencesChanged()
        # for some reason I need to post it twice to trigger a current selection's color
        setGlyphViewDisplaySettings({'OffCurvePoints':True})

    def closeWindow(self, sender):     
        self.removeObservers()
        self.handleLayer.clearSublayers()
        self.captionTextLayer.clearSublayers()
        self.ovalCurveLayer.clearSublayers()
        self.pointInsertionLayer.clearSublayers()
        self.scaleLayer.clearSublayers()
        UpdateCurrentGlyphView()

    def mouseDragged(self, point=None, delta=None):
        self.handleLayer.clearSublayers()
        self.captionTextLayer.clearSublayers()
        self.ovalCurveLayer.clearSublayers()
        self.pointInsertionLayer.clearSublayers()
        self.scaleLayer.clearSublayers()
        if self.segmentPoints:
            minX, minY, maxX, maxY  = self.getSegmentBounds(self.segmentPoints)
            scale = self.glyph.font.info.unitsPerEm/1000
            if (maxX-minX) < 20*scale:
                maxX,minX = maxY,minY
                p = int(point.y)
            else:
                p = int(point.x)
            per = round(((p - minX) * 100) / (maxX - minX)/100,5)
            if per < 0:
                per = 0
            if per > 1:
                per = 1
            # find the direction of the segment
            if self.segmentPoints[0][0] > self.segmentPoints[-1][0]:
                per = 1.0 - per
            self.percent = per
        self.drawPoints()
        
    def getModeColor(self,key,suffix):
        trySuff = suffix
        if not getDefault(f"{key}{suffix}"):
            if suffix == ".dark":
                trySuff = ""
            if not getDefault(f"{key}{trySuff}"):
                #return a fallback color
                return (.5,.5,.5,.5)
            else:
                return tuple([i for i in getDefault(f"{key}{trySuff}")])
        else:
            return tuple([i for i in getDefault(f"{key}{suffix}")])
        
    def returnSelectedContour(self,glyph):
        if glyph.contours:
            if glyph.selectedContours:
                selectedContours = [c for c in glyph.contours if c.selection][0]
                return selectedContours

    def returnSelectedSegment(self,glyph):
        contour = self.returnSelectedContour(glyph)
        if contour == None:
            pass
        else:
            return contour.selectedSegments[0]

    def returnSelectedPointsInSegment(self,glyph):
        supportedTypes = ["curve"] # working on implimenting qcurve
        segment = self.returnSelectedSegment(glyph)
        contour = self.returnSelectedContour(glyph)
        if segment != None:
            segPoints = []
            allSegs = [seg for seg in contour.segments]
            if segment.type in supportedTypes:
                segPoints.append((allSegs[segment.index-1][-1].x,allSegs[segment.index-1][-1].y))
                for selPoint in segment.points:
                    segPoints.append((selPoint.x,selPoint.y))
                return segPoints


    def returnCorrespondingPointsInSegment(self,glyph,otherFont):
        supportedTypes = ["curve"] # working on implimenting qcurve
        contour = otherFont[glyph.name].contours[self.selectedContourIndex]
        if contour:
            segment = contour.segments[self.selectedSegmentIndex]
            if segment:
                segPoints = []
            allSegs = [seg for seg in contour.segments]
            if segment.type in supportedTypes:
                segPoints.append((allSegs[segment.index-1][-1].x,allSegs[segment.index-1][-1].y))
                for selPoint in segment.points:
                    segPoints.append((selPoint.x,selPoint.y))
                return segPoints


    def getValues(self,glyph,segPoints,tVal):
        if glyph:
            glyph = glyph
            other = True
        else:
            glyph = CurrentGlyph()
            other = False
            self.segmentPoints = self.returnSelectedPointsInSegment(glyph)
            segPoints = self.segmentPoints

        if segPoints:
            r = bT.splitCubicAtT(segPoints[0],segPoints[1],segPoints[2],segPoints[3],tVal)
            UpdateCurrentGlyphView()
            return r

    def getSegmentBounds(self, segmentPoints):
        minX = min([a[0] for a in segmentPoints])
        minY = min([a[1] for a in segmentPoints])
        maxX = max([a[0] for a in segmentPoints])
        maxY = max([a[1] for a in segmentPoints])
        return minX, minY, maxX, maxY 

    def returnRatio(self,cs):
        left = self.calculateDistance(cs[0][2][0], cs[0][2][1], cs[0][3][0], cs[0][3][1])
        right = self.calculateDistance(cs[1][1][0], cs[1][1][1], cs[1][0][0], cs[1][0][1])
        if right == 0:
            ratio = 0.0
        else:
            ratio = round(left/right,3) 
        return ratio

    def returnAngles(self,cs,roundValue):
        rawAngle = math.atan2(cs[0][2][1]-cs[1][1][1], cs[0][2][0]-cs[1][1][0]) + .5 * math.pi
        fixedAngle = round( abs( math.degrees( rawAngle ) ) % 180, roundValue)
        return rawAngle, fixedAngle
        
    def calculateDistance(self,x1,y1,x2,y2):  
        dist = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)  
        return dist  

    def checkCompatible(self, fontLists):
        return [fs for fs in fontLists if self.glyph.isCompatible(fs[self.glyph.name]) and (len([point for contour in self.glyph.contours for point in contour.points]) == len([point for contour in fs[self.glyph.name].contours for point in contour.points]))]

    def getPotentialAngleMapping(self, segPoints, font):
        return {self.returnAngles(self.getValues(font[self.glyph.name],segPoints,round(a/360,4)),0)[1] : round(a/360,4) for a in range(360)} 

    def getPotentialRatioMapping(self, segPoints, font):
        return {(a/100) : round(self.returnRatio( self.getValues(font[self.glyph.name], segPoints, (a/100))),2) for a in range(100)} 
  
    
    def keyDown(self, event):
        char = event.characters()
        self.glyph = CurrentGlyph()
        selectedContours = [c for c in self.glyph.contours if c.selection]
        
        currentAngle = self.returnAngles(self.getValues([self.glyph], self.segmentPoints, self.percent),0)[1]
        currentRatio = round(self.returnRatio(self.getValues([self.glyph], self.segmentPoints, self.percent)), 2)
        
        if len(selectedContours) == 1:
            contour = selectedContours[0]
            if contour.selectedSegments:
                self.selectedContourIndex = contour.index
                self.selectedSegmentIndex = contour.selectedSegments[0].index

                # Insert point in all fonts
                if char == "A":
                    allAngles = {}
                    allRatios = {}
                    for font in self.checkCompatible(AllFonts()):
                        otherSegmentPoints = self.returnCorrespondingPointsInSegment(self.glyph, font)
                        if otherSegmentPoints:
                            potAngles = self.getPotentialAngleMapping(otherSegmentPoints,font)
                            potRatios = self.getPotentialRatioMapping(otherSegmentPoints,font)
                            otherAngleT = potAngles.get(currentAngle)
                            otherRatioT = min(potRatios.items(), key=lambda x: abs(currentRatio - x[1]))[0]
                            allAngles[font] = otherAngleT
                            allRatios[font] = otherRatioT
                        
                
                    if None not in allAngles.values():
                        PostBannerNotification("BezierSurgeon", f"Inserting point in AllFonts at an angle of {currentAngle}")
                        for font,otherAngleT in allAngles.items():
                            if font != self.glyph.font:
                                with font[self.glyph.name].undo():
                                    otherContour = font[self.glyph.name].contours[self.selectedContourIndex]
                                    otherContour.naked().splitAndInsertPointAtSegmentAndT(self.selectedSegmentIndex, otherAngleT)
                            else:
                                with self.glyph.undo():
                                    self.playPointAnimation(self.point,5)
                                    self.playPointAnimation(self.point,8)
                                    contour.naked().splitAndInsertPointAtSegmentAndT(self.selectedSegmentIndex, self.percent)
                                

                    elif None not in allRatios.values():
                        PostBannerNotification("BezierSurgeon", f"Inserting point in AllFonts at a ratio of {currentRatio}")
                        for font,otherRatioT in allRatios.items():
                            if font != self.glyph.font:
                                with font[self.glyph.name].undo():
                                    otherContour = font[self.glyph.name].contours[self.selectedContourIndex]
                                    otherContour.naked().splitAndInsertPointAtSegmentAndT(self.selectedSegmentIndex, otherRatioT)
                            else:
                                with self.glyph.undo():
                                    self.selectedSegmentIndex = contour.selectedSegments[0].index
                                    self.playPointAnimation(self.point,5)
                                    self.playPointAnimation(self.point,8)
                                    contour.naked().splitAndInsertPointAtSegmentAndT(self.selectedSegmentIndex, self.percent)
                            
                    else:
                        PostBannerNotification("BezierSurgeon", f"Sorry, I cant insert a consistent point at either {currentAngle}° or a ratio of {currentRatio}")
                                
                # Insert point in current glyph
                elif char == "C":
                    if len(contour.selectedSegments) != 1:
                        print("only select one segment")
                    else:
                        with self.glyph.undo():
                            PostBannerNotification("BezierSurgeon", f"Inserting point in CurrentGlyph at {currentAngle}° and {currentRatio}")
                            self.playPointAnimation(self.point,5)
                            self.playPointAnimation(self.point,8)
                            contour.naked().splitAndInsertPointAtSegmentAndT(contour.selectedSegments[0].index, self.percent)


                # Insert point in all fonts at specified ratio
                elif char == "R":
                    allRatios = {}
                    for font in self.checkCompatible(AllFonts()):
                        otherSegmentPoints = self.returnCorrespondingPointsInSegment(self.glyph, font)
                        if otherSegmentPoints:
                            potRatios = self.getPotentialRatioMapping(otherSegmentPoints,font)
                            otherRatioT = min(potRatios.items(), key=lambda x: abs(currentRatio - x[1]))[0]
                            allRatios[font] = otherRatioT

                    if None not in allRatios.values():
                        PostBannerNotification("BezierSurgeon", f"Inserting point in AllFonts at a ratio of {currentRatio}")
                        for font,otherRatioT in allRatios.items():
                            if font != self.glyph.font:
                                with font[self.glyph.name].undo():
                                    otherContour = font[self.glyph.name].contours[self.selectedContourIndex]
                                    otherContour.naked().splitAndInsertPointAtSegmentAndT(self.selectedSegmentIndex, otherRatioT)
                            else:
                                with self.glyph.undo():
                                    self.playPointAnimation(self.point,5)
                                    self.playPointAnimation(self.point,8)
                                    self.selectedSegmentIndex = contour.selectedSegments[0].index
                                    contour.naked().splitAndInsertPointAtSegmentAndT(self.selectedSegmentIndex, self.percent)



    def drawPoints(self):
        self.glyph = CurrentGlyph()
        
        if "qcurve" in [p.type for c in self.glyph.contours for p in c.points]:
            curveType = "Quad"
        else:
            curveType = "Cubic"
        self.offCurveStroke = self.getModeColor(f"glyphViewOffCurve{curveType}PointsStroke",self.suffix)
        
        self.upmScale = (self.glyph.font.info.unitsPerEm/1000) 

        if self.segmentPoints:
            fsp = [(float(sgp[0]),float(sgp[1])) for sgp in self.segmentPoints]
        else:
            self.segmentPoints = []
            fsp = []
            
        newPoints = self.getValues(None,fsp,self.percent)
        if newPoints != None:
            # thanks Erik!
            textLoc = newPoints[0][3][0] + math.cos(self.returnAngles(newPoints,10)[0]) * (.25*80*self.upmScale) * 2, newPoints[0][3][1] + math.sin(self.returnAngles(newPoints,10)[0]) * (.25*80*self.upmScale) * 2
            ratioFormat = "{:.2f}".format(round(self.returnRatio(newPoints),2))
            angleFormat = "{:.2f}".format(self.returnAngles(newPoints,2)[1])
            self.caption(textLoc, f'{angleFormat}° \n{ratioFormat}', (.5, 0,  1, 0.8))
            # self.drawScales((textLoc[0],textLoc[1]+60), (.5, 0,  1, 0.8), self.percent)

        if self.glyph:
            for contour in self.glyph.contours:
                for ps in contour.points:
                    if ps.type != "offcurve":
                        bPoint = RBPoint()
                        bPoint._setPoint(ps)
                        bPoint.contour = contour

                        bIn = (float(bPoint.bcpIn[0] + bPoint.anchor[0]), float(bPoint.bcpIn[1] + bPoint.anchor[1]))
                        bOut = (float(bPoint.bcpOut[0] + bPoint.anchor[0]), float(bPoint.bcpOut[1] + bPoint.anchor[1]))

                        if bIn in fsp:
                            pass
                        else:
                            self.drawHandle((bIn,bPoint.anchor),self.handleStroke,self.handleWidth)

                        if bOut in fsp:
                            pass
                        else:
                            self.drawHandle((bPoint.anchor,bOut),self.handleStroke,self.handleWidth)
                    else:
                        if (ps.x,ps.y) in fsp or (ps.x,ps.y) in fsp:
                            pass
                        else:
                            self.drawOffcurve("oval", (ps.x,ps.y), self.offCurveSize, self.offCurveFill, self.offCurveStroke, self.strokeWidth)


        newPoints = self.getValues(None,fsp,self.percent)
        if newPoints != None:
            
            self.drawHandle((newPoints[0][2],newPoints[1][1]),self.handleStroke,.5)
            self.drawHandle((newPoints[0][0],newPoints[0][1]),self.handleStroke,.5)
            self.drawHandle((newPoints[1][-1],newPoints[1][-2]),self.handleStroke,.5)

            angle = self.returnAngles(newPoints,0)[1]
            for b in newPoints:
                for a in b:
                    if a == newPoints[0][0] or a == newPoints[1][-1]:
                        pass
                    else:
                        if a == newPoints[1][0] or a == newPoints[0][-1]:
                            indicator = self.onCurveSize+5
                            # mark the point on specific angles
                            if angle in [0,45,90,135,180,225,270,315,360]:
                                self.drawOffcurve("star", (a[0],a[1]), indicator, self.onCurveFill, self.onCurveStroke, self.strokeWidth)
                            self.drawOffcurve("oval", (a[0],a[1]), self.offCurveSize, self.onCurveFill, self.onCurveStroke, self.strokeWidth)
                            self.point = (a[0],a[1])
                        else:
                            self.drawOffcurve("oval", (a[0],a[1]), self.offCurveSize, self.offCurveFill, self.offCurveStroke, self.strokeWidth)


    def playPointAnimation(self, location, size):
        x, y = location

        size *= self.upmScale
        pathLayer = self.pointInsertionLayer.appendBaseSublayer(
            position=((x-size/2, y-size/2)),
            size=(size, size),
        )

        circle = pathLayer.appendOvalSublayer(
            # position=(0, 0),
            size=(size, size),
            fillColor=None,
            strokeColor=self.onCurveStroke,
            strokeWidth=2,
            strokeCap="round")

        size *= 2.2
        with circle.propertyGroup(duration=self.duration):
            circle.setStrokeWidth(1)
            circle.setSize((size,size))

        with pathLayer.propertyGroup(
                duration=self.duration,
                animationFinishedCallback=self.removePointAnimation
            ):
            pathLayer.setOpacity(0)
            pathLayer.setPosition((x-size/2, y-size/2))


    def removePointAnimation(self, layer):
        self.pointInsertionLayer.removeSublayer(layer)

    def drawHandle(self, location, handleStrokeColor, strokeWidth):
        start,end = location
        self.handleLayer.appendLineSublayer(
           startPoint = start,
           endPoint = end,
           strokeWidth = strokeWidth,
           strokeColor = handleStrokeColor
        )

    def drawOffcurve(self, shape, location, pointSize, pointFillColor, pointStrokeColor, strokeWidth):
        pointSize *= 1.3
        self.ovalCurveLayer.appendSymbolSublayer(
            position=location,
            imageSettings=dict(
                name=shape,
                size=(pointSize,pointSize),
                fillColor = pointFillColor,
                strokeColor = pointStrokeColor,
                strokeWidth = strokeWidth,
            )
        )

    def caption(self, location, text, color):
        
        if self.mode == "dark":
            backColor = color
            frColor = (1,1,1,1)
        else:
            backColor = (.5, 0,  1, 0.2)
            frColor = color
            
        self.captionTextLayer.appendTextLineSublayer(
           position=location,
           pointSize=int(getDefault('textFontSize')) + 2,
           backgroundColor=backColor,
           text=f"{text}",
           fillColor=frColor,
           horizontalAlignment="center",
           verticalAlignment="bottom",
           weight='bold',
           figureStyle='tabular',
           padding=(10,10),
           cornerRadius = 5
        )


    def interpolatePoints(self, a, b, v):
        x = a[0] + v * (b[0] - a[0])
        y = a[1] + v * (b[1] - a[1])
        return (x,y)


    def drawScales(self, location, color, tValue):
        x,y = location
        start,end = (x-50,y),(x+50,y)

        dot = self.interpolatePoints(end,start,tValue)

        self.scaleLayer.appendLineSublayer(
           startPoint = start,
           endPoint = end,
           strokeWidth = 2,
           strokeColor = color
        )

        startDot = self.scaleLayer.appendSymbolSublayer(
            position=start,
            imageSettings=dict(
                name="oval",
                size=(6,6),
                fillColor = color,
                strokeColor = color,
                strokeWidth = 2,
            )
        )

        endDot = self.scaleLayer.appendSymbolSublayer(
            position=end,
            imageSettings=dict(
                name="oval",
                size=(6,6),
                fillColor = color,
                strokeColor = color,
                strokeWidth = 2,
            )
        )

        endDot = self.scaleLayer.appendSymbolSublayer(
            position=dot,
            imageSettings=dict(
                name="oval",
                size=(6,6),
                fillColor = color,
                strokeColor = color,
                strokeWidth = 2,
            )
        )


# -----------------------------------------        
# -----------------------------------------

    def becomeInactive(self):
        self.closeWindow(None)

    def dragSelection(self, point, delta):
        if self.getValues(None,self.segmentPoints,self.percent):
            return
        super().dragSelection(point, delta)      

    def getToolbarTip(self):
        return "Bezier Surgeon"

    def getToolbarIcon(self):
        return toolbarIcon
        
    def canSelectWithMarque(self):
        return False
        
    
if __name__ == '__main__':
    BezierSurgeon = BezierSurgeon()
    installTool(BezierSurgeon)
