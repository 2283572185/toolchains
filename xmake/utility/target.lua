---@alias modifier_t fun(target:string):nil
---@alias modifier_table_t table<string, modifier_t>

---占位符，无效果
---@return nil
function noop_modifier(_) return end

---为loongnix定制部分flag
---@return nil
function loongnix_modifier(toolchain)
    -- loongnix的glibc版本较老，使用的ld路径与新编译器默认路径不同
    toolchain:add("ldflags", "-Wl,-dynamic-linker=/lib64/ld.so.1")
    -- loongnix本机gdb仅支持dwarf4格式调试信息
    toolchain:add("cxflags", "-gdwarf-4")
end

---为独立工具链定值部分flag
---@return nil
function freestanding_modifier(toolchain)
    -- freestanding需要禁用标准库
    toolchain:add("cxflags", "-ffreestanding", "-nostdlib")
    toolchain:add("ldflags", "-nostdlib")
end

---只有clang支持的目标
---@type modifier_table_t
clang_only_target_list = { ["x86_64-windows-msvc"] = noop_modifier }
---gcc和clang均支持的目标
---@type modifier_table_t
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
---所有受支持的目标
---@type modifier_table_t
target_list = table.join(general_target_list, clang_only_target_list)

---获取只有clang支持的目标列表
---@return modifier_table_t
function get_clang_only_target_list()
    return clang_only_target_list
end

---获取gcc和clang均支持的目标列表
---@return modifier_table_t
function get_general_target_list()
    return general_target_list
end

---获取所有受支持的目标列表
---@return modifier_table_t
function get_target_list()
    return target_list
end
