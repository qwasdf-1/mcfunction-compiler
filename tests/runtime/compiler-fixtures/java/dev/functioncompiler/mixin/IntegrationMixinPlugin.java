package dev.functioncompiler.mixin;

import java.util.List;
import java.util.Set;
import org.objectweb.asm.tree.ClassNode;
import org.spongepowered.asm.mixin.extensibility.IMixinConfigPlugin;
import org.spongepowered.asm.mixin.extensibility.IMixinInfo;

/** Test-only scoreboard observers are not installed in ordinary runs. */
public final class IntegrationMixinPlugin implements IMixinConfigPlugin {
    private static boolean flag(String name) {
        return Boolean.parseBoolean(System.getenv(name));
    }
    @Override public boolean shouldApplyMixin(String target, String mixin) {
        if (mixin.endsWith(".ScoreLifecycleFixtureMixin"))
            return flag("FC_TYPED_IR046_TEST_OBSERVER") || flag("FC_TYPED_IR047_TEST_OBSERVER");
        if (mixin.endsWith(".ScoreboardQueueInjectionMixin"))
            return flag("FC_TYPED_IR_REENTRANT_TEST_OBSERVER");
        if (mixin.endsWith(".IR048BuildContextsFixtureMixin")
                || mixin.endsWith(".IR048ContextChainFixtureMixin")
                || mixin.endsWith(".IR048FunctionBuilderFixtureMixin"))
            return flag("FC_IR048_CENSUS");
        return true;
    }
    @Override public void onLoad(String pkg) {}
    @Override public String getRefMapperConfig() { return null; }
    @Override public void acceptTargets(Set<String> mine, Set<String> other) {}
    @Override public List<String> getMixins() { return null; }
    @Override public void preApply(String target, ClassNode node, String mixin, IMixinInfo info) {}
    @Override public void postApply(String target, ClassNode node, String mixin, IMixinInfo info) {}
}
