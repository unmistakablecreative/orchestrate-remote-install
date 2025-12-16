#target photoshop

/**
 * photoshop_core.jsx - Primitive-based Photoshop automation
 *
 * Reads operation sequence from ~/orchestrate/data/adobe_config.json
 * Writes result to ~/orchestrate/data/adobe_result.json
 */

// JSON polyfill for ExtendScript
if (typeof JSON === 'undefined') {
    JSON = {};
    JSON.parse = function(s) {
        return eval('(' + s + ')');
    };
    JSON.stringify = function(obj) {
        if (obj === null) return 'null';
        if (typeof obj === 'undefined') return undefined;
        if (typeof obj === 'number' || typeof obj === 'boolean') return String(obj);
        if (typeof obj === 'string') return '"' + obj.replace(/"/g, '\\"') + '"';
        if (obj instanceof Array) {
            var arr = [];
            for (var i = 0; i < obj.length; i++) {
                arr.push(JSON.stringify(obj[i]));
            }
            return '[' + arr.join(',') + ']';
        }
        if (typeof obj === 'object') {
            var pairs = [];
            for (var k in obj) {
                if (obj.hasOwnProperty(k)) {
                    pairs.push('"' + k + '":' + JSON.stringify(obj[k]));
                }
            }
            return '{' + pairs.join(',') + '}';
        }
        return String(obj);
    };
}

// Helper to convert hex color to SolidColor
function hexToSolidColor(hex) {
    hex = hex.replace('#', '');
    var color = new SolidColor();
    color.rgb.red = parseInt(hex.substring(0, 2), 16);
    color.rgb.green = parseInt(hex.substring(2, 4), 16);
    color.rgb.blue = parseInt(hex.substring(4, 6), 16);
    return color;
}

// Helper to get layer by name
function getLayerByName(name) {
    var doc = app.activeDocument;
    try {
        return doc.artLayers.getByName(name);
    } catch (e) {
        // Try layer sets too
        try {
            return doc.layerSets.getByName(name);
        } catch (e2) {
            return null;
        }
    }
}

// Primitive implementations
var primitives = {

    createDocument: function(params) {
        var width = new UnitValue(params.width, "px");
        var height = new UnitValue(params.height, "px");
        var name = params.name || "Untitled";
        var colorMode = params.colorMode || "RGB";

        var mode = NewDocumentMode.RGB;
        if (colorMode === "CMYK") mode = NewDocumentMode.CMYK;
        if (colorMode === "Grayscale") mode = NewDocumentMode.GRAYSCALE;

        var doc = app.documents.add(width, height, 72, name, mode);
        return {created: name, width: params.width, height: params.height};
    },

    openDocument: function(params) {
        var file = new File(params.path);
        if (!file.exists) {
            throw new Error("File not found: " + params.path);
        }
        var doc = app.open(file);
        return {opened: params.path};
    },

    addTextLayer: function(params) {
        var doc = app.activeDocument;
        var layer = doc.artLayers.add();
        layer.kind = LayerKind.TEXT;

        var textItem = layer.textItem;
        textItem.contents = params.text;

        if (params.font) {
            textItem.font = params.font;
        }
        if (params.size) {
            textItem.size = new UnitValue(params.size, "pt");
        }
        if (params.color) {
            textItem.color = hexToSolidColor(params.color);
        }

        textItem.position = [new UnitValue(params.x, "px"), new UnitValue(params.y, "px")];

        layer.name = params.text.substring(0, 30);

        return {added: "text", name: layer.name};
    },

    addShapeLayer: function(params) {
        var doc = app.activeDocument;
        var type = params.type;
        var shapeParams = params.params;

        // Create a new layer for the shape
        var shapeLayer = doc.artLayers.add();
        shapeLayer.name = type + "_shape";

        // Create selection based on shape type
        if (type === "rectangle") {
            var bounds = [
                [shapeParams.x, shapeParams.y],
                [shapeParams.x + shapeParams.width, shapeParams.y],
                [shapeParams.x + shapeParams.width, shapeParams.y + shapeParams.height],
                [shapeParams.x, shapeParams.y + shapeParams.height]
            ];
            doc.selection.select(bounds);
        } else if (type === "ellipse") {
            // Use ellipse selection region
            var left = shapeParams.x - shapeParams.width / 2;
            var top = shapeParams.y - shapeParams.height / 2;
            var right = shapeParams.x + shapeParams.width / 2;
            var bottom = shapeParams.y + shapeParams.height / 2;
            var selRegion = [[left, top], [right, top], [right, bottom], [left, bottom]];
            doc.selection.select(selRegion, SelectionType.REPLACE, 0, false);
            // Now use elliptical selection
            doc.selection.deselect();
            var idsetd = charIDToTypeID("setd");
            var desc = new ActionDescriptor();
            var idnull = charIDToTypeID("null");
            var ref = new ActionReference();
            var idChnl = charIDToTypeID("Chnl");
            var idfsel = charIDToTypeID("fsel");
            ref.putProperty(idChnl, idfsel);
            desc.putReference(idnull, ref);
            var idT = charIDToTypeID("T   ");
            var descEllipse = new ActionDescriptor();
            var idTop = charIDToTypeID("Top ");
            var idPxl = charIDToTypeID("#Pxl");
            descEllipse.putUnitDouble(idTop, idPxl, top);
            var idLeft = charIDToTypeID("Left");
            descEllipse.putUnitDouble(idLeft, idPxl, left);
            var idBtom = charIDToTypeID("Btom");
            descEllipse.putUnitDouble(idBtom, idPxl, bottom);
            var idRght = charIDToTypeID("Rght");
            descEllipse.putUnitDouble(idRght, idPxl, right);
            var idElps = charIDToTypeID("Elps");
            desc.putObject(idT, idElps, descEllipse);
            executeAction(idsetd, desc, DialogModes.NO);
        }

        // Fill selection with color
        var fillColor = hexToSolidColor(shapeParams.fillColor || shapeParams.color || "#ffffff");
        doc.selection.fill(fillColor);
        doc.selection.deselect();

        return {added: "shape", type: type};
    },

    applyGradient: function(params) {
        var doc = app.activeDocument;
        var layer = getLayerByName(params.layer);

        if (layer) {
            doc.activeLayer = layer;
        }

        var startColor = params.startColor.replace('#', '');
        var endColor = params.endColor.replace('#', '');
        var angle = params.angle || 90;

        // Select all
        doc.selection.selectAll();

        // Use Action Manager for gradient fill
        var idGrdn = charIDToTypeID("Grdn");
        var desc = new ActionDescriptor();

        // Gradient descriptor
        var idGrad = charIDToTypeID("Grad");
        var descGrad = new ActionDescriptor();
        var idNm = charIDToTypeID("Nm  ");
        descGrad.putString(idNm, "Custom Gradient");
        var idGrdF = charIDToTypeID("GrdF");
        var idGrFr = charIDToTypeID("GrFr");
        var idClrS = charIDToTypeID("ClrS");
        descGrad.putEnumerated(idGrdF, idGrFr, idClrS);
        var idIntr = charIDToTypeID("Intr");
        descGrad.putDouble(idIntr, 4096);

        // Color stops
        var idClrs = charIDToTypeID("Clrs");
        var listClrs = new ActionList();

        // Start color stop
        var descStop1 = new ActionDescriptor();
        var idClr = charIDToTypeID("Clr ");
        var descClr1 = new ActionDescriptor();
        descClr1.putDouble(charIDToTypeID("Rd  "), parseInt(startColor.substring(0, 2), 16));
        descClr1.putDouble(charIDToTypeID("Grn "), parseInt(startColor.substring(2, 4), 16));
        descClr1.putDouble(charIDToTypeID("Bl  "), parseInt(startColor.substring(4, 6), 16));
        descStop1.putObject(idClr, charIDToTypeID("RGBC"), descClr1);
        var idType = charIDToTypeID("Type");
        var idClry = charIDToTypeID("Clry");
        var idUsrS = charIDToTypeID("UsrS");
        descStop1.putEnumerated(idType, idClry, idUsrS);
        var idLctn = charIDToTypeID("Lctn");
        descStop1.putInteger(idLctn, 0);
        var idMdpn = charIDToTypeID("Mdpn");
        descStop1.putInteger(idMdpn, 50);
        var idClrt = charIDToTypeID("Clrt");
        listClrs.putObject(idClrt, descStop1);

        // End color stop
        var descStop2 = new ActionDescriptor();
        var descClr2 = new ActionDescriptor();
        descClr2.putDouble(charIDToTypeID("Rd  "), parseInt(endColor.substring(0, 2), 16));
        descClr2.putDouble(charIDToTypeID("Grn "), parseInt(endColor.substring(2, 4), 16));
        descClr2.putDouble(charIDToTypeID("Bl  "), parseInt(endColor.substring(4, 6), 16));
        descStop2.putObject(idClr, charIDToTypeID("RGBC"), descClr2);
        descStop2.putEnumerated(idType, idClry, idUsrS);
        descStop2.putInteger(idLctn, 4096);
        descStop2.putInteger(idMdpn, 50);
        listClrs.putObject(idClrt, descStop2);

        descGrad.putList(idClrs, listClrs);

        // Transparency stops
        var idTrns = charIDToTypeID("Trns");
        var listTrns = new ActionList();
        var descTrns1 = new ActionDescriptor();
        var idOpct = charIDToTypeID("Opct");
        var idPrc = charIDToTypeID("#Prc");
        descTrns1.putUnitDouble(idOpct, idPrc, 100);
        descTrns1.putInteger(idLctn, 0);
        descTrns1.putInteger(idMdpn, 50);
        var idTrnS = charIDToTypeID("TrnS");
        listTrns.putObject(idTrnS, descTrns1);
        var descTrns2 = new ActionDescriptor();
        descTrns2.putUnitDouble(idOpct, idPrc, 100);
        descTrns2.putInteger(idLctn, 4096);
        descTrns2.putInteger(idMdpn, 50);
        listTrns.putObject(idTrnS, descTrns2);
        descGrad.putList(idTrns, listTrns);

        desc.putObject(idGrad, idGrad, descGrad);

        // Angle
        var idAngl = charIDToTypeID("Angl");
        var idAng = charIDToTypeID("#Ang");
        desc.putUnitDouble(idAngl, idAng, angle);

        // Type (linear)
        var idType = charIDToTypeID("Type");
        var idGrdT = charIDToTypeID("GrdT");
        var idLnr = charIDToTypeID("Lnr ");
        desc.putEnumerated(idType, idGrdT, idLnr);

        executeAction(idGrdn, desc, DialogModes.NO);

        doc.selection.deselect();

        return {applied: "gradient", layer: params.layer};
    },

    applyEffect: function(params) {
        var doc = app.activeDocument;
        var layer = getLayerByName(params.layer);

        if (!layer) {
            throw new Error("Layer not found: " + params.layer);
        }

        doc.activeLayer = layer;
        var effectName = params.effectName;
        var effectParams = params.params;

        // Apply effect via action manager (more reliable)
        var idsetd = charIDToTypeID("setd");
        var desc = new ActionDescriptor();
        var idnull = charIDToTypeID("null");
        var ref = new ActionReference();
        var idPrpr = charIDToTypeID("Prpr");
        var idLefx = charIDToTypeID("Lefx");
        ref.putProperty(idPrpr, idLefx);
        var idLyr = charIDToTypeID("Lyr ");
        var idOrdn = charIDToTypeID("Ordn");
        var idTrgt = charIDToTypeID("Trgt");
        ref.putEnumerated(idLyr, idOrdn, idTrgt);
        desc.putReference(idnull, ref);

        var idT = charIDToTypeID("T   ");
        var descEffect = new ActionDescriptor();
        var idScl = charIDToTypeID("Scl ");
        var idPrc = charIDToTypeID("#Prc");
        descEffect.putUnitDouble(idScl, idPrc, 100);

        if (effectName === "dropShadow") {
            var idDrSh = charIDToTypeID("DrSh");
            var descShadow = new ActionDescriptor();
            var idenab = charIDToTypeID("enab");
            descShadow.putBoolean(idenab, true);
            var idMd = charIDToTypeID("Md  ");
            var idBlnM = charIDToTypeID("BlnM");
            var idMltp = charIDToTypeID("Mltp");
            descShadow.putEnumerated(idMd, idBlnM, idMltp);
            var idOpct = charIDToTypeID("Opct");
            descShadow.putUnitDouble(idOpct, idPrc, effectParams.opacity || 75);
            var idDstn = charIDToTypeID("Dstn");
            descShadow.putUnitDouble(idDstn, charIDToTypeID("#Pxl"), effectParams.distance || 5);
            var idblur = charIDToTypeID("blur");
            descShadow.putUnitDouble(idblur, charIDToTypeID("#Pxl"), effectParams.blur || 5);
            descEffect.putObject(idDrSh, idDrSh, descShadow);
        }

        var idLefx = charIDToTypeID("Lefx");
        desc.putObject(idT, idLefx, descEffect);
        executeAction(idsetd, desc, DialogModes.NO);

        return {applied: effectName, layer: params.layer};
    },

    importImage: function(params) {
        var doc = app.activeDocument;
        var file = new File(params.path);

        if (!file.exists) {
            throw new Error("Image file not found: " + params.path);
        }

        // Place embedded
        var idPlc = charIDToTypeID("Plc ");
        var desc = new ActionDescriptor();
        var idnull = charIDToTypeID("null");
        desc.putPath(idnull, file);
        var idFTcs = charIDToTypeID("FTcs");
        var idQCSt = charIDToTypeID("QCSt");
        var idQcsa = charIDToTypeID("Qcsa");
        desc.putEnumerated(idFTcs, idQCSt, idQcsa);

        if (params.width || params.height) {
            var idWdth = charIDToTypeID("Wdth");
            var idHght = charIDToTypeID("Hght");
            var idPxl = charIDToTypeID("#Pxl");
            if (params.width) desc.putUnitDouble(idWdth, idPxl, params.width);
            if (params.height) desc.putUnitDouble(idHght, idPxl, params.height);
        }

        var idOfst = charIDToTypeID("Ofst");
        var descOfst = new ActionDescriptor();
        var idHrzn = charIDToTypeID("Hrzn");
        var idVrtc = charIDToTypeID("Vrtc");
        var idPxl = charIDToTypeID("#Pxl");
        descOfst.putUnitDouble(idHrzn, idPxl, params.x);
        descOfst.putUnitDouble(idVrtc, idPxl, params.y);
        desc.putObject(idOfst, idOfst, descOfst);

        executeAction(idPlc, desc, DialogModes.NO);

        // Commit the placement
        var idplacedLayerEditContents = stringIDToTypeID("placedLayerEditContents");
        var desc2 = new ActionDescriptor();
        try {
            executeAction(stringIDToTypeID("placeEvent"), desc, DialogModes.NO);
        } catch (e) {
            // Already placed
        }

        // If removeBackground is requested, apply it to the just-placed layer
        if (params.removeBackground) {
            var placedLayerName = doc.activeLayer.name;
            primitives.removeBackground({layer: placedLayerName});
        }

        return {imported: params.path, x: params.x, y: params.y, backgroundRemoved: params.removeBackground || false};
    },

    setLayerOpacity: function(params) {
        var layer = getLayerByName(params.layer);
        if (!layer) {
            throw new Error("Layer not found: " + params.layer);
        }
        layer.opacity = params.opacity;
        return {set: "opacity", layer: params.layer, value: params.opacity};
    },

    setLayerBlendMode: function(params) {
        var layer = getLayerByName(params.layer);
        if (!layer) {
            throw new Error("Layer not found: " + params.layer);
        }

        var modes = {
            "normal": BlendMode.NORMAL,
            "multiply": BlendMode.MULTIPLY,
            "screen": BlendMode.SCREEN,
            "overlay": BlendMode.OVERLAY,
            "softlight": BlendMode.SOFTLIGHT,
            "hardlight": BlendMode.HARDLIGHT,
            "colorburn": BlendMode.COLORBURN,
            "colordodge": BlendMode.COLORDODGE
        };

        var mode = modes[params.mode.toLowerCase()];
        if (mode) {
            layer.blendMode = mode;
        }

        return {set: "blendMode", layer: params.layer, value: params.mode};
    },

    resizeCanvas: function(params) {
        var doc = app.activeDocument;
        var anchor = params.anchor || AnchorPosition.MIDDLECENTER;

        doc.resizeCanvas(
            new UnitValue(params.width, "px"),
            new UnitValue(params.height, "px"),
            anchor
        );

        return {resized: "canvas", width: params.width, height: params.height};
    },

    flattenLayers: function(params) {
        var doc = app.activeDocument;
        doc.flatten();
        return {flattened: true};
    },

    exportPNG: function(params) {
        var doc = app.activeDocument;
        var file = new File(params.path);

        var opts = new PNGSaveOptions();
        opts.compression = 6;
        opts.interlaced = false;

        doc.saveAs(file, opts, true, Extension.LOWERCASE);

        return {exported: params.path, format: "PNG"};
    },

    exportJPG: function(params) {
        var doc = app.activeDocument;
        var file = new File(params.path);

        var opts = new JPEGSaveOptions();
        opts.quality = params.quality || 12;
        opts.embedColorProfile = true;
        opts.formatOptions = FormatOptions.STANDARDBASELINE;

        doc.saveAs(file, opts, true, Extension.LOWERCASE);

        return {exported: params.path, format: "JPG", quality: opts.quality};
    },

    saveDocument: function(params) {
        var doc = app.activeDocument;
        var file = new File(params.path);

        doc.saveAs(file);

        return {saved: params.path};
    },

    closeDocument: function(params) {
        var doc = app.activeDocument;
        var saveOption = params.save ? SaveOptions.SAVECHANGES : SaveOptions.DONOTSAVECHANGES;
        doc.close(saveOption);
        return {closed: true, saved: params.save || false};
    },

    removeBackground: function(params) {
        var doc = app.activeDocument;
        var layer = getLayerByName(params.layer);

        if (layer) {
            doc.activeLayer = layer;
        }

        var targetLayer = doc.activeLayer;

        // CRITICAL: Convert background layer to regular layer BEFORE any operations
        // This must happen first - cannot clear on background layers
        if (targetLayer.isBackgroundLayer) {
            targetLayer.isBackgroundLayer = false;
        }

        // Method 1: autoCutout to select subject, invert, clear (preferred method)
        try {
            var idautoCutout = stringIDToTypeID("autoCutout");
            var desc = new ActionDescriptor();
            var idsampleAllLayers = stringIDToTypeID("sampleAllLayers");
            desc.putBoolean(idsampleAllLayers, false);
            executeAction(idautoCutout, desc, DialogModes.NO);

            // autoCutout selects the SUBJECT - invert to select BACKGROUND
            doc.selection.invert();

            // Clear the background (selection is now background)
            doc.selection.clear();
            doc.selection.deselect();

            return {removed: "background", method: "autoCutoutClear"};
        } catch (e) {
            // autoCutout not available, continue to fallback
        }

        // Method 2: Try Photoshop's native Remove Background (CC 2021+)
        try {
            var idremoveBackground = stringIDToTypeID("removeBackground");
            executeAction(idremoveBackground, undefined, DialogModes.NO);
            return {removed: "background", method: "nativeRemoveBackground"};
        } catch (e) {
            // Native not available, continue to fallback
        }

        // Method 3: Magic Wand fallback - select background areas, clear
        try {
            // Select corners (typical background areas) via magic wand
            var idMWnd = charIDToTypeID("setd");
            var descWand = new ActionDescriptor();
            var idnull = charIDToTypeID("null");
            var ref = new ActionReference();
            ref.putProperty(charIDToTypeID("Chnl"), charIDToTypeID("fsel"));
            descWand.putReference(idnull, ref);
            var idT = charIDToTypeID("T   ");
            var descPt = new ActionDescriptor();
            descPt.putUnitDouble(charIDToTypeID("Hrzn"), charIDToTypeID("#Pxl"), 5);
            descPt.putUnitDouble(charIDToTypeID("Vrtc"), charIDToTypeID("#Pxl"), 5);
            descWand.putObject(idT, charIDToTypeID("Pnt "), descPt);
            var idTlrn = charIDToTypeID("Tlrn");
            descWand.putInteger(idTlrn, 32);
            var idAntA = charIDToTypeID("AntA");
            descWand.putBoolean(idAntA, true);
            var idCntg = charIDToTypeID("Cntg");
            descWand.putBoolean(idCntg, true);
            executeAction(idMWnd, descWand, DialogModes.NO);

            // Grow selection to catch similar background areas
            try {
                var idGrow = charIDToTypeID("Grow");
                var descGrow = new ActionDescriptor();
                descGrow.putInteger(charIDToTypeID("Tlrn"), 32);
                descGrow.putBoolean(charIDToTypeID("AntA"), true);
                executeAction(idGrow, descGrow, DialogModes.NO);
            } catch (growErr) {
                // Grow not critical
            }

            // Background is selected - clear it
            doc.selection.clear();
            doc.selection.deselect();

            return {removed: "background", method: "magicWandClear"};
        } catch (e2) {
            return {removed: "background", method: "failed", error: e2.message};
        }
    },

    runAction: function(params) {
        var actionSet = params.actionSet;
        var actionName = params.actionName;

        try {
            app.doAction(actionName, actionSet);
            return {ran: "action", actionSet: actionSet, actionName: actionName};
        } catch (e) {
            throw new Error("Action failed: " + actionSet + "/" + actionName + " - " + e.message);
        }
    }
};

// Main execution
function main() {
    // Read config
    var configFile = new File("~/orchestrate/data/adobe_config.json");
    if (!configFile.exists) {
        throw new Error("Config file not found: ~/orchestrate/data/adobe_config.json");
    }

    configFile.open("r");
    var configText = configFile.read();
    configFile.close();

    var config = JSON.parse(configText);

    // Initialize result
    var result = {
        success: true,
        operations_completed: 0,
        operations_total: config.operations.length,
        output: null,
        details: []
    };

    // Execute operations in sequence
    try {
        for (var i = 0; i < config.operations.length; i++) {
            var op = config.operations[i];
            var fn = op.fn;

            if (primitives[fn]) {
                var opResult = primitives[fn](op);
                result.operations_completed++;
                result.details.push({op: fn, index: i, result: opResult});
            } else {
                throw new Error("Unknown primitive: " + fn);
            }
        }
        result.output = config.output;
    } catch (e) {
        result.success = false;
        result.error = e.message;
        result.failed_at = result.operations_completed;
    }

    // Write result
    var resultFile = new File("~/orchestrate/data/adobe_result.json");
    resultFile.open("w");
    resultFile.write(JSON.stringify(result));
    resultFile.close();

    return result;
}

// Run
main();
