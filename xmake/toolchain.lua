---@type string | nil
local rcfiles = os.getenv("XMAKE_RCFILES")
---@type string | nil
local script_dir = nil
---探测toolchain.lua并根据该文件的绝对路径提取脚本目录
---@see https://github.com/xmake-io/xmake/issues/6048
if rcfiles then
    for _, rcfile in ipairs(path.splitenv(rcfiles)) do
        if rcfile:endswith("toolchain.lua") then
            script_dir = path.directory(rcfile)
            break
        end
    end
end

if script_dir then
    add_moduledirs(script_dir)
    includes(path.join(script_dir, "option.lua"), path.join(script_dir, "utility/target.lua"))
else
    includes("option.lua", "utility/target.lua")
end

---获取工具链描述文本
---@param toolchain string --工具链名称
---@param target string --工具链目标
---@return string --描述文本
function _get_toolchain_description(toolchain, target)
    return format("A %s toolchain for ", toolchain) ..
        (target ~= "target" and target or "target detected by arch and plat")
end

---注册clang工具链
---@param target string --clang工具链目标平台
---@param modifier modifier_t --回调函数，为target定制一些flag
---@return nil
function register_clang_toolchain(target, modifier)
    toolchain(target .. "-clang", function()
        set_kind("standalone")
        set_homepage("https://github.com/24bit-xjkp/toolchains/")
        set_description(_get_toolchain_description("clang", target))
        set_runtimes("c++_static", "c++_shared", "stdc++_static", "stdc++_shared")

        set_toolset("cc", "clang")
        set_toolset("cxx", "clang++", "clang")
        set_toolset("ld", "clang++", "clang")
        set_toolset("sh", "clang++", "clang")
        set_toolset("as", "clang")
        set_toolset("ar", "llvm-ar")
        set_toolset("strip", "llvm-strip")
        set_toolset("ranlib", "llvm-ranlib")
        set_toolset("objcopy", "llvm-objcopy")
        set_toolset("mrc", "llvm-rc")

        on_check(function(_)
            return import("lib.detect.find_program")("clang")
        end)

        on_load(function(toolchain)
            import("utility.utility")
            if toolchain:is_plat("windows") then
                toolchain:add("runtimes", "MT", "MTd", "MD", "MDd")
            end

            if target == "target" then
                target, modifier = utility.get_target_modifier()
            end

            toolchain:add("cxflags", utility.get_march_option(target, "clang"))
            local sysroot_option = utility.get_sysroot_option()
            for flag, option in pairs(sysroot_option) do
                toolchain:add(flag, option)
            end

            local rtlib_option = utility.get_rtlib_option()
            local unwind_option = utility.get_unwindlib_option()
            for _, flag in ipairs({ "cxflags", "ldflags", "shflags" }) do
                toolchain:add(flag, target ~= "native" and "--target=" .. target or nil)
                toolchain:add(flag ~= "cxflags" and flag or nil, rtlib_option, unwind_option)
            end

            modifier(toolchain)
        end)
    end)
end

for target, modifier in pairs(target_list) do
    register_clang_toolchain(target, modifier)
end

---注册gcc工具链
---@param target string --gcc工具链目标平台
---@param modifier modifier_t --回调函数，为target定制一些flag
---@return nil
function register_gcc_toolchain(target, modifier)
    toolchain(target .. "-gcc", function()
        set_kind("standalone")
        set_homepage("https://github.com/24bit-xjkp/toolchains/")
        set_description(_get_toolchain_description("gcc", target))
        set_runtimes("stdc++_static", "stdc++_shared")
        local prefix

        on_check(function(_)
            if target == "target" then
                target, modifier = import("utility.utility").get_target_modifier()
            end
            prefix = target == "native" and "" or target .. "-"
            return import("lib.detect.find_program")(prefix .. "gcc")
        end)

        on_load(function(toolchain)
            prefix = target == "native" and "" or target .. "-"
            toolchain:set("toolset", "cc", prefix .. "gcc")
            toolchain:set("toolset", "cxx", prefix .. "g++", prefix .. "gcc")
            toolchain:set("toolset", "ld", prefix .. "g++", prefix .. "gcc")
            toolchain:set("toolset", "sh", prefix .. "g++", prefix .. "gcc")
            toolchain:set("toolset", "ar", prefix .. "ar")
            toolchain:set("toolset", "strip", prefix .. "strip")
            toolchain:set("toolset", "objcopy", prefix .. "objcopy")
            toolchain:set("toolset", "ranlib", prefix .. "ranlib")
            toolchain:set("toolset", "as", prefix .. "gcc")

            import("utility.utility")
            toolchain:add("cxflags", utility.get_march_option(target, "gcc"))
            local sysroot_option = utility.get_sysroot_option()
            for flag, option in pairs(sysroot_option) do
                toolchain:add(flag, option)
            end

            modifier(toolchain)
        end)
    end)
end

for target, modifier in pairs(general_target_list) do
    register_gcc_toolchain(target, modifier)
end
