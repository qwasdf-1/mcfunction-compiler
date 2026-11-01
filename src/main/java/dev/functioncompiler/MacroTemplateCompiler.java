package dev.functioncompiler;

import dev.functioncompiler.mixin.MacroFunctionAccessor;
import net.minecraft.commands.functions.MacroFunction;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.DoubleTag;
import net.minecraft.nbt.FloatTag;
import net.minecraft.nbt.NumericTag;
import net.minecraft.nbt.StringTag;
import net.minecraft.nbt.Tag;

import java.text.DecimalFormat;
import java.text.DecimalFormatSymbols;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

final class MacroTemplateCompiler {
    private static final DecimalFormat DECIMAL_FORMAT;

    static {
        DECIMAL_FORMAT = new DecimalFormat("#", DecimalFormatSymbols.getInstance(Locale.ROOT));
        DECIMAL_FORMAT.setMaximumFractionDigits(15);
    }

    private MacroTemplateCompiler() {
    }

    static List<String> extractArguments(MacroFunction<?> macro, CompoundTag arguments) {
        if (arguments == null) {
            return null;
        }
        List<String> parameters = ((MacroFunctionAccessor) macro).functionCompiler$getParameters();
        List<String> values = new ArrayList<>(parameters.size());
        for (String param : parameters) {
            Tag tag = arguments.get(param);
            if (tag == null) {
                return null;
            }
            values.add(stringify(tag));
        }
        return values;
    }

    private static String stringify(Tag tag) {
        if (tag instanceof StringTag stringTag) {
            return stringTag.value();
        }
        if (tag instanceof DoubleTag doubleTag) {
            return DECIMAL_FORMAT.format(doubleTag.value());
        }
        if (tag instanceof FloatTag floatTag) {
            return DECIMAL_FORMAT.format(floatTag.value());
        }
        if (tag instanceof NumericTag numericTag) {
            return String.valueOf(numericTag.longValue());
        }
        return tag.toString();
    }
}
