-- 占位符，无效果
function noop_modifier(_) return end

-- 为loongnix定制部分flag
function loongnix_modifier(toolchain)
    -- loongnix的glibc版本较老，使用的ld路径与新编译器默认路径不同
    toolchain:add("ldflags", "-Wl,-dynamic-linker=/lib64/ld.so.1")
    -- loongnix本机gdb仅支持dwarf4格式调试信息
    toolchain:add("cxflags", "-gdwarf-4")
end

-- 为独立工具链定值部分flag
function freestanding_modifier(toolchain)
    -- freestanding需要禁用标准库
    toolchain:add("cxflags", "-ffreestanding", "-nostdlib")
    toolchain:add("ldflags", "-nostdlib")
end

-- 只有clang支持的目标
clang_only_target_list = { ["x86_64-windows-msvc"] = noop_modifier }
-- gcc和clang均支持的目标
general_target_list = {
    ["x86_64-linux-gnu"] = noop_modifier,
    ["i686-linux-gnu"] = noop_modifier,
    ["x86_64-w64-mingw32"] = noop_modifier,
    ["i686-w64-mingw32"] = noop_modifier,
    ["loongarch64-linux-gnu"] = noop_modifier,
    ["loongarch64-loongnix-linux-gnu"] = loongnix_modifier,
    ["riscv64-linux-gnu"] = noop_modifier,
    ["aarch64-linux-gnu"] = noop_modifier,
    ["arm-linux-gnueabi"] = noop_modifier,
    ["arm-linux-gnueabihf"] = noop_modifier,
    ["arm-none-eabi"] = freestanding_modifier,
    ["x86_64-elf"] = freestanding_modifier,
    ["native"] = noop_modifier,
    ["target"] = noop_modifier
}
-- 所有受支持的目标
target_list = table.join(general_target_list, clang_only_target_list)

-- @brief 获取只有clang支持的目标列表
function get_clang_only_target_list()
    return clang_only_target_list
end

-- @brief 获取gcc和clang均支持的目标列表
function get_general_target_list()
    return general_target_list
end

-- @brief 获取所有受支持的目标列表
function get_target_list()
    return target_list
end
