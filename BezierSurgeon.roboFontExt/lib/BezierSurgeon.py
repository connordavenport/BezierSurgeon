from fontTools.misc import bezierTools as bT
import math
import mojo.drawingTools as d
from mojo.events import addObserver, removeObserver, EditingTool, installTool
from defconAppKit.windows.baseWindow import BaseWindowController
from mojo.UI import Message, getDefault, CurrentGlyphWindow, UpdateCurrentGlyphView
from vanilla import HUDFloatingWindow, Slider, SquareButton,Group
from defcon import Contour, Font
import AppKit

'''
to do:
- add batch point insertion
- add support for quadratic curves
'''

toolbarIcon = AppKit.NSImage.alloc().initByReferencingFile_("SurgeonIcon.pdf")
toolbarIcon.setTemplate_(True)

class BezierSurgeon(BaseWindowController):

    def __init__(self):

        self.w = HUDFloatingWindow((self.getWindowPostition()[0] + 25, self.getWindowPostition()[1] + 25 , 200, 60), "BezierSurgeon", closable=False)
        self.w.getNSWindow().setTitleVisibility_(True)
        self.w.getNSWindow().setTitlebarAppearsTransparent_(True)
        self.w.sliderVal = Slider(
                (10, 0, -10, 22),
                value=0.500, maxValue=1, minValue=0,
                callback=self.getValues)
        self.w.sliderVal.enable(False)
        self.w.button = SquareButton((85, 25, 30, 25), "✁", callback=self.insertPoint)
        self.w.button.enable(False)
        self.setUpBaseWindowBehavior()
        self.addObservers()
        self.w.open()


    def addObservers(self):

        addObserver(self, "drawPoints", "drawBackground")
        addObserver(self, "drawInactive", "drawInactive")


    def removeObservers(self):

        removeObserver(self, "drawBackground")
        removeObserver(self, "drawInactive")
        

    def closeWindow(self, sender):        

        self.removeObservers()
        UpdateCurrentGlyphView()
        

    def getWindowPostition(self):
        # Code from Tal
        # https://forum.robofont.com/topic/573/automatic-statusinteractivepopupwindow-positioning
        if not CurrentGlyphWindow():
            return
        nsWindow = CurrentGlyphWindow().w.getNSWindow()
        scrollView = CurrentGlyphWindow().getGlyphView().enclosingScrollView()
        rectInWindowCoords = scrollView.convertRect_toView_(scrollView.frame(), None)
        rectInScreenCoords = nsWindow.convertRectToScreen_(rectInWindowCoords)
        (x, y), (w, h) = rectInScreenCoords
        y = -(y + h)
        return x, y
        

    def returnSelectedContour(self,glyph):

        if glyph.contours:
            if glyph.selectedContours:
                selC = [c for c in glyph.contours if c.selection][0]
                return selC


    def returnSelectedSegment(self,glyph):

        contour = self.returnSelectedContour(glyph)
        if contour == None:
            self.w.sliderVal.enable(False)
            self.w.button.enable(False)
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

    def getValues(self,sender):

        glyph = CurrentGlyph()

        if glyph is not None:

            t = self.w.sliderVal.get()
            segmentPoints = self.returnSelectedPointsInSegment(glyph)

            if segmentPoints != None:

                self.w.sliderVal.enable(True)
                self.w.button.enable(True)

                r = bT.splitCubicAtT(segmentPoints[0],segmentPoints[1],segmentPoints[2],segmentPoints[3],t)

                UpdateCurrentGlyphView()

                return r


    def returnRatio(self,cs):
        left = self.calculateDistance(cs[0][2][0], cs[0][2][1], cs[0][3][0], cs[0][3][1])
        right = self.calculateDistance(cs[1][1][0], cs[1][1][1], cs[1][0][0], cs[1][0][1])
        if right == 0:
            ratio = 0.0
        else:
            ratio = round(left/right,3) 
        return ratio

    def returnAngle(self,cs):
        return math.atan2(cs[0][2][1]-cs[1][1][1], cs[0][2][0]-cs[1][1][0]) + .5 * math.pi
        
    def calculateDistance(self,x1,y1,x2,y2):  
        dist = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)  
        return dist  
    
    # insert point across all fonts
    # Thanks Mathieu Réguer!

    # def bissect(self, func, target_result, min_value, max_value, max_iter=30, margin=0.1):
    #     min_value_ = min_value
    #     max_value_ = max_value
    #     for n in range(1, max_iter + 1):
    #         mid = (min_value_ + max_value_) / 2
    #         mid_result = func(mid)
    #         if target_result - margin < mid_result < target_result + margin:
    #             return mid
    #         elif mid_result > target_result:
    #             min_value_ = min_value_
    #             max_value_ = mid
    #         elif mid_result < target_result:
    #             min_value_ = mid
    #             max_value_ = max_value_

    #     return mid

    # def returnTValue(self, points, wantedAngle):

    #     # points 

    #     def getAngle(t):

    #         return angle

    #     # Annnd bissect that function
    #     resultT = self.bissect(getAngle, wantedAngle, 0, 1)
    #     return resultT


    def insertPoint(self,sender):

        t = self.w.sliderVal.get()
        newPoints = self.getValues(None)
        
        glyph = CurrentGlyph()

        selC = [c for c in glyph.contours if c.selection]
        if selC != []:
            if len(selC) != 1:
                pass
            else:
                contour = selC[0]
                if len(contour.selectedSegments) != 1:
                    print("only select one segment")
                else:
                    glyph.prepareUndo("insertPoint")
                    contour.naked().splitAndInsertPointAtSegmentAndT(contour.selectedSegments[0].index, t)
                    contour.selectedSegments = []
                    glyph.performUndo()


    def drawPoints(self, info):
    
        newPoints = self.getValues(None)
        if newPoints != None:
            glyph = CurrentGlyph()
        
            onCurveSize = getDefault("glyphViewOncurvePointsSize") * 5
            offCurveSize = getDefault("glyphViewOncurvePointsSize") * 3
            fillColor = tuple([i for i in getDefault("glyphViewCurvePointsFill")])
        
            upmScale = (glyph.font.info.unitsPerEm/1000) 
            scale = info["scale"]
            oPtSize = onCurveSize * scale
            fPtSize = offCurveSize * scale

            d.save()

            # thanks Erik!
            textLoc = newPoints[0][3][0] + math.cos(self.returnAngle(newPoints)) * (scale*.25*120) * 2, newPoints[0][3][1] + math.sin(self.returnAngle(newPoints)) * (scale*.25*120) * 2

            for b in newPoints:
                for a in b:
                    if a == newPoints[1][0] or a == newPoints[0][-1]:
                        d.oval(a[0]-oPtSize/2,a[1]-oPtSize/2, oPtSize, oPtSize) 
                    else:
                        d.oval(a[0]-fPtSize/2,a[1]-fPtSize/2, fPtSize, fPtSize) 
                    d.fill(fillColor[0],fillColor[1],fillColor[2],fillColor[3])
        
            d.stroke(fillColor[0],fillColor[1],fillColor[2],fillColor[3])
            d.strokeWidth(scale)
            d.line(newPoints[0][2],newPoints[1][1])
            d.restore()

            # https://robofont.com/documentation/building-tools/toolspace/observers/draw-info-text-in-glyph-view/?highlight=draw%20text

            glyphWindow = CurrentGlyphWindow()
            if not glyphWindow:
                return
            glyphView = glyphWindow.getGlyphView()
            textAttributes = {
                AppKit.NSFontAttributeName: AppKit.NSFont.userFixedPitchFontOfSize_(11),
            }
            glyphView.drawTextAtPoint(
            f'{round(abs(math.degrees(self.returnAngle(newPoints)))%180,4)}°\n{str(round(self.returnRatio(newPoints),4))}',
            textAttributes,
            textLoc,
            yOffset=0,
            drawBackground=True,
            centerX=True,
            centerY=True,
            roundBackground=False,)

            UpdateCurrentGlyphView()

    def drawInactive(self,info):
        self.drawPoints(info)
        
class SurgeonTool(EditingTool):
    
    def becomeActive(self):
        self.SurgeonToolUI = BezierSurgeon()
    
    def becomeInactive(self):
        self.SurgeonToolUI.closeWindow(None)
        self.SurgeonToolUI.w.close()

    def glyphWindowDidOpen(self, info):
        self.SurgeonToolUI.w.show()

    def glyphWindowWillClose(self,info):
        # print("becomeInactive_noWindow")
        self.SurgeonToolUI.closeWindow(None)
        self.SurgeonToolUI.w.hide()

    def getToolbarTip(self):
        return "Bezier Surgeon"

    def getToolbarIcon(self):
        return toolbarIcon
        
installTool(SurgeonTool())