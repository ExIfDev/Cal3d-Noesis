#written by Aexadev on 12/12/2025
from inc_noesis import *
import noesis, rapi # type: ignore
import xml.etree.ElementTree as ET
import re


def registerNoesisTypes():

    
    hmdl = noesis.register("Cal3d mesh file", ".cmf")
    noesis.setHandlerTypeCheck(hmdl, ChkMdl)
    noesis.setHandlerLoadModel(hmdl, LoadMdl)
    return 1

def ChkMdl(data):
    bs  = NoeBitStream(data)
    val = bs.readBytes(4)
    return 1 if val == b"CMF\x00" else 0

def LoadMdl(data, mdl_list):
    bs = NoeBitStream(data)
    rapi.rpgCreateContext() 
    
    cfg = LoadConfig()
    
    #SKELETON
    if cfg["skeleton"]:
        bones = LoadSkeleton(rapi.getDirForFilePath(rapi.getInputName())+cfg["skeleton"])
    
    MESH_FILE_COUNT = len(cfg["meshes"])
    matList = []
    matCache = {}
    for _ in range(MESH_FILE_COUNT):
        
        filePth = rapi.getDirForFilePath(rapi.getInputName())+cfg["meshes"][_]
        print(filePth)
        fileDat = rapi.loadIntoByteArray(filePth)
        MESH_NAME = rapi.getExtensionlessName(cfg["meshes"][_])
        bs = NoeBitStream(fileDat)

        vBuf = bytearray()
        iBuf = bytearray()
        nBuf = bytearray()
        uvBuf = bytearray()
        
        bs.readBytes(4)
        FILE_VER = bs.readInt()
        MESH_COUNT = bs.readInt()
        
        print("ver: ",FILE_VER, "Mcnt: ",MESH_COUNT)
        #noesis.doException("end")
        
        for m in range(MESH_COUNT):
            MAT_ID = bs.readInt()
            VTX_COUNT = bs.readInt()
            FACE_COUNT = bs.readInt()
            LOD_STEPS = bs.readInt()
            SPRING_COUNT = bs.readInt()
            TEX_COUNT = bs.readInt()
            if FILE_VER >= 1200:
                MORPH_COUNT = bs.readInt()

            print(MAT_ID, VTX_COUNT, FACE_COUNT, SPRING_COUNT, TEX_COUNT)

            vBuf = bytearray()
            nBuf = bytearray()
            uv1Buf = bytearray()
            uv2Buf = bytearray()
            iBuf = bytearray()
            boneIdxBuf = bytearray()
            boneWgtBuf = bytearray()

            # VERTICES
            for _ in range(VTX_COUNT):
                vBuf.extend(bs.readBytes(12))  # pos
                nBuf.extend(bs.readBytes(12))  # nrm
                COL_ID = bs.readInt()
                FCCOL_CNT = bs.readInt()
                #UV
                if TEX_COUNT >= 1:
                    uv1Buf.extend(bs.readBytes(8))

                if TEX_COUNT >= 2:
                    uv2Buf.extend(bs.readBytes(8))
                    
                WEIGHT_COUNT = bs.readUInt()
                vBoneIds = []
                vBoneWgts = []
                for _ in range(WEIGHT_COUNT):
                    BONE_ID = bs.readUInt()
                    WEIGHT = bs.readFloat()
                    vBoneIds.append(BONE_ID)
                    vBoneWgts.append(WEIGHT)
                    
                    
                if SPRING_COUNT > 0:
                    S_WHGT = bs.readFloat()
                    
                #norm to 4 weights since it goes from 1 to 4 weights per vtx    
                while len(vBoneIds) < 4:
                    vBoneIds.append(0)
                    vBoneWgts.append(0.0)
            
                for i in range(4):
                    boneIdxBuf.extend(struct.pack("<I", vBoneIds[i]))   
                    boneWgtBuf.extend(struct.pack("<f", vBoneWgts[i])) 
                    
                    
            # SPRINGS
            for _ in range(SPRING_COUNT):
                S_VIDX1 = bs.readInt()
                S_VIDX2 = bs.readInt()
                S_COEF = bs.readFloat()
                S_IDLELEN = bs.readFloat()

            # MORPHS
            if FILE_VER >= 1200:
                for _ in range(MORPH_COUNT):
                    RP_NAME = readLenStr(bs)
                    BLND_VTXS = bs.readInt()
                    for _ in range(BLND_VTXS):
                        RP_VTXID = bs.readInt()
                        bs.readBytes(12)  # pos
                        bs.readBytes(12)  # nrm
                        for _ in range(TEX_COUNT):
                            bs.readBytes(8)  # uv

            # FACES (indices)
            faceBytes = bs.readBytes(FACE_COUNT * 12)
            iBuf.extend(faceBytes)
            
            
            #MATERIAL
            texPath = GetTexture(rapi.getDirForFilePath(rapi.getInputName()) + cfg["materials"][MAT_ID])

            if MAT_ID in matCache:
                mat = matCache[MAT_ID]
            else:
                matName = "mat_%d" % MAT_ID   
                mat = NoeMaterial(matName, texPath)
                mat.flags |= noesis.NMATFLAG_TWOSIDED
                matList.append(mat)
                matCache[MAT_ID] = mat
            


            rapi.rpgClearBufferBinds()
            rapi.rpgSetName(MESH_NAME+"_%d" % m)
            rapi.rpgSetMaterial(mat.name) 
            rapi.rpgBindPositionBuffer(vBuf, noesis.RPGEODATA_FLOAT, 12)
            rapi.rpgBindNormalBuffer(nBuf, noesis.RPGEODATA_FLOAT, 12)
            if uv1Buf:
                rapi.rpgBindUV1Buffer(uv1Buf, noesis.RPGEODATA_FLOAT, 8)
            if uv2Buf:
                rapi.rpgBindUV2Buffer(uv2Buf, noesis.RPGEODATA_FLOAT, 8)
            if bones:
                rapi.rpgBindBoneIndexBuffer(boneIdxBuf, noesis.RPGEODATA_UINT, 16, 4)
                rapi.rpgBindBoneWeightBuffer(boneWgtBuf, noesis.RPGEODATA_FLOAT, 16, 4)
                
            rapi.rpgCommitTriangles(iBuf, noesis.RPGEODATA_UINT, FACE_COUNT * 3, noesis.RPGEO_TRIANGLE)

    
    
    mdl = rapi.rpgConstructModel()
    #mdl = NoeModel()
    mdl.setModelMaterials(NoeModelMaterials([], matList))
    if bones:
        mdl.setBones(bones)
        rapi.setPreviewOption("setSkelToShow", "1")
    rapi.processCommands("-rotate 90 0 0")
    mdl_list.append(mdl)
    return 1



def LoadConfig():
    baseDir = rapi.getDirForFilePath(rapi.getInputName())
    for f in os.listdir(baseDir):
        if f.lower().endswith(".cfg"):
            cfgPath = os.path.join(baseDir, f)
            
    cfgData = rapi.loadIntoByteArray(cfgPath)
    text = cfgData.decode("ascii", "ignore")

    cfg = {
        "scale": 1.0,
        "skeleton": None,
        "animations": [],
        "meshes": [],
        "materials": [],
    }

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        if "=" not in line:
            continue

        key, value = [p.strip() for p in line.split("=", 1)]

        if key == "scale":
            try:
                cfg["scale"] = float(value)
            except ValueError:
                pass
        elif key == "skeleton":
            cfg["skeleton"] = value
        elif key == "animation":
            cfg["animations"].append(value)
        elif key == "mesh":
            cfg["meshes"].append(value)
        elif key == "material":
            cfg["materials"].append(value)

    return cfg

def readLenStr(bs):
    sl = bs.readUInt()
    if sl == 0:
        return ""
    raw = bs.readBytes(sl)
    return raw.split(b"\x00", 1)[0].decode("ascii", "ignore")

def GetTexture(path):

    data = rapi.loadIntoByteArray(path)
    text = data.decode("utf-8", "ignore")
    text = text.lstrip("\ufeff")

    match = re.search(r"<MAP>(.*?)</MAP>", text, re.IGNORECASE | re.DOTALL)
    if not match:
        print("GetTexture: no tex found in", path)
        return None

    texname = match.group(1).strip()



    baseDir = rapi.getDirForFilePath(path)
    texpath = os.path.join(baseDir, texname)

    print("TEXPATH ",texpath)

    return texpath


def LoadSkeleton(path):
    #credit to Durik256
    data = rapi.loadIntoByteArray(path)
    print("SKEL PATH: ",path)
    
    bs = NoeBitStream(data)
    
    bs.seek(8)
    
    bones = []
    for x in range(bs.readInt()):
        name = noeAsciiFromBytes(bs.readBytes(bs.readInt()))
        pos = NoeVec3.fromBytes(bs.readBytes(12))
        rot = NoeQuat.fromBytes(bs.readBytes(16)).toMat43()
        rot[3] = pos
        bs.seek(28,1)
        parent = bs.readInt()
        bs.seek(bs.readInt()*4,1)
        bones.append(NoeBone(x, name, rot, None, parent))


    bones = rapi.multiplyBones(bones)
    return bones
    
    
    