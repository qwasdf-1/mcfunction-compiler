package dev.functioncompiler;

import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.execution.UnboundEntryAction;
import org.objectweb.asm.ClassWriter;
import org.objectweb.asm.MethodVisitor;
import org.objectweb.asm.Opcodes;

import java.lang.invoke.MethodHandles;
import java.lang.invoke.MethodType;
import java.util.concurrent.atomic.AtomicLong;

/**
 * IR-025 actual JVM bytecode emitter for the parsed native-selector fork plan.
 * The generated action runs at the exact original function source index;
 * it does NOT forward the whole fork to original BuildContexts on the
 * validated fast path. All specialized per-fork work lives in the shared,
 * audited executor, and native selector/continuation/terminal remain native.
 */
final class CompilerForkBytecode025 implements Opcodes {
    private static final AtomicLong IDS = new AtomicLong();
    private static final String ACTION =
            "net/minecraft/commands/execution/UnboundEntryAction";
    private static final String SOURCE =
            "net/minecraft/commands/CommandSourceStack";
    private static final String EXEC =
            "net/minecraft/commands/execution/ExecutionContext";
    private static final String FRAME =
            "net/minecraft/commands/execution/Frame";
    private static final String PLAN =
            "dev/functioncompiler/CompilerForkPlan024$Plan";
    private static final String RUNTIME =
            "dev/functioncompiler/CompilerForkExecutor025";
    private static final String EXECUTE =
            "(Ljava/lang/Object;L" + EXEC + ";L" + FRAME + ";)V";

    private CompilerForkBytecode025() {}

    @SuppressWarnings("unchecked")
    static UnboundEntryAction<CommandSourceStack> emit(
            CompilerForkPlan024.Plan plan,
            UnboundEntryAction<CommandSourceStack> original
    ) {
        String internal = "dev/functioncompiler/CompiledFork025$Generated$"
                + IDS.incrementAndGet();
        byte[] bytes = generate(internal);
        try {
            MethodHandles.Lookup lookup = MethodHandles.lookup().defineHiddenClass(
                    bytes, true, MethodHandles.Lookup.ClassOption.NESTMATE);
            var constructor = lookup.findConstructor(
                    lookup.lookupClass(),
                    MethodType.methodType(void.class,
                            CompilerForkPlan024.Plan.class, UnboundEntryAction.class));
            return (UnboundEntryAction<CommandSourceStack>) constructor.invoke(
                    plan, original);
        } catch (Throwable failure) {
            if (failure instanceof Error error) throw error;
            if (failure instanceof RuntimeException runtime) throw runtime;
            throw new IllegalStateException("IR025 generated fork action couldn't load", failure);
        }
    }

    private static byte[] generate(String internal) {
        ClassWriter writer = new ClassWriter(
                ClassWriter.COMPUTE_FRAMES | ClassWriter.COMPUTE_MAXS);
        writer.visit(V17, ACC_FINAL | ACC_SUPER, internal, null,
                "java/lang/Object", new String[]{ACTION});
        writer.visitField(ACC_PRIVATE | ACC_FINAL, "plan", "L" + PLAN + ";", null, null)
                .visitEnd();
        writer.visitField(ACC_PRIVATE | ACC_FINAL, "original", "L" + ACTION + ";",
                null, null).visitEnd();
        MethodVisitor constructor = writer.visitMethod(ACC_PUBLIC, "<init>",
                "(L" + PLAN + ";L" + ACTION + ";)V", null, null);
        constructor.visitCode();
        constructor.visitVarInsn(ALOAD, 0);
        constructor.visitMethodInsn(INVOKESPECIAL, "java/lang/Object", "<init>",
                "()V", false);
        constructor.visitVarInsn(ALOAD, 0);
        constructor.visitVarInsn(ALOAD, 1);
        constructor.visitFieldInsn(PUTFIELD, internal, "plan", "L" + PLAN + ";");
        constructor.visitVarInsn(ALOAD, 0);
        constructor.visitVarInsn(ALOAD, 2);
        constructor.visitFieldInsn(PUTFIELD, internal, "original", "L" + ACTION + ";");
        constructor.visitInsn(RETURN);
        constructor.visitMaxs(0, 0);
        constructor.visitEnd();

        MethodVisitor execute = writer.visitMethod(ACC_PUBLIC, "execute",
                EXECUTE, null, null);
        execute.visitCode();
        execute.visitVarInsn(ALOAD, 0);
        execute.visitFieldInsn(GETFIELD, internal, "plan", "L" + PLAN + ";");
        execute.visitVarInsn(ALOAD, 0);
        execute.visitFieldInsn(GETFIELD, internal, "original", "L" + ACTION + ";");
        execute.visitVarInsn(ALOAD, 1);
        execute.visitTypeInsn(CHECKCAST, SOURCE);
        execute.visitVarInsn(ALOAD, 2);
        execute.visitVarInsn(ALOAD, 3);
        execute.visitMethodInsn(INVOKESTATIC, RUNTIME, "run",
                "(L" + PLAN + ";L" + ACTION + ";L" + SOURCE + ";L"
                        + EXEC + ";L" + FRAME + ";)V", false);
        execute.visitInsn(RETURN);
        execute.visitMaxs(0, 0);
        execute.visitEnd();
        writer.visitEnd();
        return writer.toByteArray();
    }
}
