#!/usr/bin/python3.9
import os
import re
import sys
import argparse
import logging

#Utilities to read Gcode lines into Python data structures.
#gcode lines are stored into dictionnaries with each key corresponding
#to a token that was detected in said line.
def readGcodeLine(line: str):
    '''
    Parse a Gcode line and return the tokens that were
    understood in a dictionnary. Do nothing to tokens that
    were not understood. Based on regexp.

    line is a string containing a Gcode line.
    '''
    typeOfLinePattern = r"^(;)|([G]\d+)"

    #the pipe is a regex "or"
    coordinatePattern = r"[XYZE](([+-]?)"\
            + r"(((\d+)(\.\d+)?)"\
            + r"|([+-]?(\d*)(\.\d+))))"
    #potential concern here: will match XYZE followed by nothing.
    #will crash later in that case

    typeOfLineMatch   = re.search(typeOfLinePattern, line)

    ##Initialize output dictionnary
    output = {}

    #Check type of line:
    ##If a re.match does not find anything, the returned type is
    ##none, which does not have a "group" method.
    if isinstance(typeOfLineMatch, re.Match):
        if (typeOfLineMatch.group(0)[0]==";"):
            output["type"] = "comment"
            return output
        else:
            output["type"] = typeOfLineMatch.group(0)
    else:
        #logging.warning("Type of line not detected:%s", line)
        output["type"] = "unknown"

    coordinateMatches = re.finditer(coordinatePattern, line)
    #Process coordinate matches
    for match in coordinateMatches:
        #determine axis of coordinate
        fullMatch = match.group(0)
        if fullMatch[0]=="F":
            output["F"] = float(match.group(1))
        if fullMatch[0]=="X":
            output["X"] = float(match.group(1))
        elif fullMatch[0]=="Y":
            output["Y"] = float(match.group(1))
        elif fullMatch[0]=="Z":
            output["Z"] = float(match.group(1))
        elif fullMatch[0]=="E":
            output["E"] = float(match.group(1))
    return output

def hasCoordinate( gcodeLine : dict ):
    '''
    Determine if the gcode line contains spatial information.
    '''
    if 'X' in gcodeLine or 'Y' in gcodeLine or 'Z' in gcodeLine:
        return True
    else:
        return False

def hasExtrusion( gcodeLine: dict ):
    '''
    Determines if the gcode line describes extrusion.
    '''
    if hasCoordinate( gcodeLine ) and 'E' in gcodeLine:
        if gcodeLine['E'] > 0:
            return True
    else:
        return False

def getPoint( gcodeLine: dict, currPoint: tuple ):
    '''
    Determines if the gcode line describes a new point.
    '''
    x, y, z = currPoint
    hasPoint = False
    if 'X' in gcodeLine:
        #update X
        x = gcodeLine['X']
        hasPoint = True
    if 'Y' in gcodeLine:
        #update Y
        y = gcodeLine['Y']
        hasPoint = True
    if 'Z' in gcodeLine:
        #update Z:
        z = gcodeLine['Z']
        hasPoint = True
    if hasPoint:
        return (x, y, z)
    else:
        return ()

def readGcodeFile(File: str):
    '''
    Read Gcode file and stores lines with extrusion.

    File is a string with the path to the gcode file.
    segmentList will be a list of entries with 2 entries in R3,
    corresponding to the lines with extrusion in File.
    '''
    #initialize two empty dictionnaries for
    #the previous line and the current line
    currLine = {}
    #initialize segmentList to empty list
    pointList = []
    connectivity = []
    with open(File, 'r') as FileHandle:
        lines = FileHandle.readlines()

        prevPoint = (0.0, 0.0, 0.0)
        currPoint = (0.0, 0.0, 0.0)

        #read lines
        for line in lines:

            currLine = readGcodeLine( line )

            if currLine["type"] == "comment":
                continue

            #contains a point?
            newPoint = getPoint(currLine, currPoint)
            if newPoint:
                prevPoint = currPoint
                currPoint = newPoint

            #if line has extrusion, store the associated segment and points
            if hasExtrusion(currLine):
                #add the previously read point only
                #if it isn't the equal to the last point added.
                if pointList:
                    if prevPoint != pointList[-1]:
                        pointList.append( prevPoint )
                else:
                    pointList.append( prevPoint )

                pointList.append( currPoint )
                #zero indexing
                connectivity.append( (len(pointList)-2, len(pointList)-1) )

        return pointList, connectivity

def write2TxtFile( file:str,
        pointList: list[tuple], connectivity: list[tuple]):
    '''
    Write points and connectivities to .txt
    '''
    with open(file, 'w') as f:
        #write points
        ##points header
        pointsHeader = "POINTS " + str(len(pointList)) + "\n"
        f.write(pointsHeader)
        ##points
        for p in pointList:
            #write the tuple without its parentheses
            f.write( str(p)[1:-1]  + "\n")

        #write connectivities
        ##header
        linesHeader = "LINES " + str(len(connectivity)) + "\n"
        f.write(linesHeader)
        ##lines
        for l in connectivity:
            #write the tuple without its parentheses
            f.write( str(l)[1:-1] + "\n" )
    return

def write2VtkFile( file:str,
        pointList: list[tuple], connectivity: list[tuple], scaling=1e-3):
    '''
    Write points and connectivities to .txt
    '''
    numPoints = len(pointList)
    numLines = len(connectivity)
    with open(file, 'w') as f:
        #write header
        f.write("# vtk DataFile Version 2.0\n")
        #write title
        f.write("Some gcode\n")
        #write data type
        f.write("ASCII\n")
        #write geometry
        f.write("DATASET POLYDATA\n")
        ##points
        f.write("POINTS " + str(numPoints) + " float\n")
        for p in pointList:
            #scaling, the output is a list
            p = [scaling * x for x in p]
            #convert list to string without brackets and commas
            tmp = " ".join( repr(e) for e in p )
            f.write( tmp + "\n" )
        ##lines
        f.write("LINES " + str(numLines) + " " + str(3*numLines) + "\n")
        for l in connectivity:
            #write the tuple without its parentheses and commas
            tmp = "2 " + re.sub( r"[,()]", "", str(l))
            f.write( tmp + "\n" )
    return

def testLineReader():
    lines = ["G1 X4.4 Y-4.4 Z0.3 E0.33107 asdasdasd",\
        "G00",\
        "G0 F7200 X68.135 Y-.319",
        "TIME",
        "G0 F7200 X Y-.319",
        "X4.4 Y-4.4 Z0.3 E0.33107 asdasdasd"]
    print("Trying out line reader...")
    for line in lines:
        print(line)
        output = readGcodeLine(line)
        print(output)

def testFileReader():
    file = "gcodes/tests/SkipComments.gcode"

    print("Trying out file reader...")
    print("Target:", file)
    p, c = readGcodeFile( file )

    print("Trying out .txt writer...")
    txt = "out.txt"
    write2TxtFile( txt, p, c )
    print("Wrote to " + txt + "." )

    print("Trying out .vtk writer...")
    vtk = "out.vtk"
    write2VtkFile( vtk, p, c )
    print("Wrote to " + vtk + "." )
if __name__=="__main__":
    #get commandline arguments
    parser = argparse.ArgumentParser(description=
            "Read standard .gcode and output .vtk.")
    parser.add_argument('path2gcode', nargs=1,
            help='Path to input .gcode file.')
    parser.add_argument('path2vtk', nargs='?',
            help='Path to output .vtk file.\
                    If not provided, it will be\
                    derived from path2gcode')
    parser.add_argument('scaling', nargs='?', type=float, default=1e-3,
            help='By default values are scaled by 1e-3\
                    to change units from [mm] to [m]')

    args = parser.parse_args()

    #unpack
    path2gcode = args.path2gcode[ 0 ]
    scaling = args.scaling
    #standarize the path of the mandatory argument
    path2gcode = os.path.normcase( path2gcode )
    
    #default name of vtk file
    if not args.path2vtk:
        head = os.path.basename( path2gcode )
        head = os.path.splitext( head )[0]
        path2vtk = head + "-gcode.vtk"
    else:
        path2vtk = args.path2vtk
        path2vtk = os.path.normcase( path2vtk )

    #log file settings
    logging.basicConfig(filename="logfile", level=logging.INFO,
            format="%(levelname)s:%(message)s")
    logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))

    logging.info("Target gcode file: {}".format(path2gcode))
    logging.info("Target vtk file: {}".format(path2vtk))
    logging.info("Scaling: {}".format(str(scaling)))

    #run file reader and get points and connectivities
    p, c = readGcodeFile( path2gcode )

    #run vtk writer and write to path2vtk
    write2VtkFile( path2vtk, p, c, scaling )
