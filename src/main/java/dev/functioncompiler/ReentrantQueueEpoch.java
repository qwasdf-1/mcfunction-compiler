package dev.functioncompiler;

/**
 * IR-013 research-only queue staging generation.
 *
 * A synchronous mod/command callback may append work while a generated IR
 * region is still executing its original commands. Staging is only flushed
 * between ExecutionContext queue actions. Reading an epoch allows the region
 * to yield at the first subsequent original command boundary, without
 * changing the normal queue scheduler or scanning the staged queue.
 */
public interface ReentrantQueueEpoch {
    long functionCompiler$queuedWorkEpoch();
}
