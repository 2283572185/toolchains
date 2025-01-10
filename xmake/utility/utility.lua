import("core.cache.detectcache")
---@alias map_t table<string, string>

---判断工具链是否是clang
---@return boolean --是否是clang工具链
function _is_clang()
    return string.find(get_config("toolchain") or "", "clang", 1, true) ~= nil
end

---本模块使用的缓存键
local cache_key = "toolchain.utility"

---获取缓存信息
---@return table<string, any> --缓存信息表
function _get_cache()
    local cache_info = detectcache:get(cache_key)
    if not cache_info then
        cache_info = {}
        detectcache:set(cache_key, cache_info)
    end
    return cache_info
end

---更新缓存信息
---@param cache_info table --要保存的缓存信息
---@return nil
function _update_cache(cache_info)
    detectcache:set(cache_key, cache_info)
    detectcache:save()
end

---根据arch和plat推导target和modifier
---@param toolchain string --工具链名称
---@return string --目标平台
---@return modifier_t --调整函数
function get_target_modifier(toolchain)
    ---@type table<string, any>
    local cache_info = _get_cache()
    ---@type string, modifier_t
    local target, modifier = table.unpack(cache_info["target"] or {})
    if target and modifier then -- 已经探测过，直接返回target和modifier
        return target, modifier
    end

    ---@type string | nil
    local arch = get_config("arch")
    ---@type string | nil
    local plat = get_config("plat")
    ---@type string
    local target_os = get_config("target_os") or "none"
    local message = [[Unsupported %s "%s". Please select a specific toolchain.]]

    ---将xmake风格arch映射为triplet风格
    ---@type map_t
    local arch_table = {
        x86 = "i686",
        i386 = "i686",
        i686 = "i686",
        x64 = "x86_64",
        x86_64 = "x86_64",
        loong64 = "loongarch64",
        riscv64 = "riscv64",
        arm = "arm",
        armv7 = "arm",
        armv7s = "arm",
        ["arm64-v8a"] = "aarch64",
        arm64 = "aarch64",
        arm64ec = "aarch64"
    }
    local old_arch = arch
    arch = arch_table[arch]
    assert(arch, format(message, "arch", old_arch))

    if plat == "windows" and toolchain == "gcc" then
        plat = "mingw" -- gcc不支持msvc目标，但clang支持
    end
    ---@type map_t
    local plat_table = {
        mingw = "w64",
        msys = "w64",
        linux = "linux",
        windows = "windows",
        cross = target_os
    }
    local old_plat = plat
    plat = plat_table[plat]
    assert(plat, format(message, "plat", old_plat))

    ---@type map_t
    local x86_abi_table = {
        windows = "msvc",
        w64 = "mingw32",
        linux = "gnu",
        none = "elf"
    }
    ---@type map_t
    local linux_abi_table = { linux = "gnu" }
    ---@type table<string, map_t>
    local abi_table = {
        i686 = x86_abi_table,
        x86_64 = x86_abi_table,
        arm = {
            linux = "gnueabihf",
            none = "eabi"
        },
        aarch64 = linux_abi_table,
        riscv64 = linux_abi_table,
        loongarch64 = linux_abi_table
    }
    ---@type string
    local abi = (abi_table[arch] or {})[plat] or "unknown"

    ---@type string[]
    local field = { arch, plat, abi }
    -- 针对arch-elf的特殊处理
    if plat == "none" and abi == "elf" then
        table.remove(field, 2)
    end
    target = table.concat(field, "-")

    modifier = import("target", { anonymous = true }).get_target_list()[target]
    cprint("detecting for target .. " .. (modifier and "${color.success}" or "${color.failure}") .. target)
    assert(modifier, format(message, "target", target))

    cache_info["target"] = { target, modifier }
    _update_cache(cache_info)

    return target, modifier
end

---根据选项或探测结果获取sysroot选项列表
---@return table<string, string | string[]> | nil --选项列表
function get_sysroot_option()
    local cache_info = _get_cache()
    ---sysroot缓存
    ---@type string | nil
    local sysroot = cache_info["sysroot"]
    ---根据sysroot获取选项列表
    ---@return table<string, string | string[]> --选项列表
    local function get_option_list()
        local sysroot_option = "--sysroot=" .. sysroot
        -- 判断是不是libc++
        local is_libcxx = (get_config("runtimes") or ""):startswith("c++")
        local libcxx_option = is_libcxx and "-isystem" .. path.join(sysroot, "include", "c++", "v1") or nil
        return { cxflags = { sysroot_option, libcxx_option }, ldflags = sysroot_option, shflags = sysroot_option }
    end
    if sysroot == "" then
        return nil               -- 已经探测过，无sysroot可用
    elseif sysroot then
        return get_option_list() -- 已经探测过，使用缓存的sysroot
    end

    -- 检查给定sysroot或者自动探测sysroot
    sysroot = get_config("sysroot")
    local detect = sysroot == "detect"
    -- sysroot不为"no"或"detect"则为指定的sysroot
    sysroot = (sysroot ~= "no" and not detect) and sysroot or nil
    -- 若使用clang工具链且未指定sysroot则尝试自动探测
    detect = detect and _is_clang()
    if sysroot then    -- 有指定sysroot则检查合法性
        assert(os.isdir(sysroot), string.format([[The sysroot "%s" is not a directory.]], sysroot))
    elseif detect then -- 尝试探测
        ---@type string | nil
        local prefix = get_config("bin") or try { function() return os.iorunv("llvm-config", { "--prefix" }) end }
        if prefix then
            -- 尝试下列目录：1. prefix/sysroot 2. prefix/../sysroot 优先使用更局部的目录
            for _, v in ipairs({ "sysroot", "../sysroot" }) do
                local dir = path.join(prefix, v)
                if os.isdir(dir) then
                    sysroot = path.normalize(dir)
                    cprint("detecting for sysroot ... ${color.success}%s", sysroot)
                    break
                end
            end
        end
    end

    -- 更新缓存
    cache_info["sysroot"] = sysroot or ""
    _update_cache(cache_info)

    if sysroot then
        return get_option_list(sysroot)
    else
        if detect then
            cprint("detecting for sysroot ... ${color.failure}no")
        end
        return nil
    end
end

---获取march选项
---@param target string --目标平台
---@param toolchain string --工具链类型
---@note 在target和toolchain存在时才检查选项合法性
---@return string | nil --march选项
function get_march_option(target, toolchain)
    local cache_info = _get_cache()
    local option = cache_info["march"]
    if option == "" then
        return nil    -- 已经探测过，-march不受支持
    elseif option then
        return option -- 已经探测过，支持-march选项
    end

    ---探测march是否受支持
    ---@type string
    local arch = get_config("march")
    if arch ~= "no" then
        local march = (arch ~= "default" and arch or "native")
        option = { "-march=" .. march }
        -- 在target和toolchain存在时才检查选项合法性
        if target and toolchain then
            import("core.tool.compiler")
            if toolchain == "clang" and target ~= "native" then
                table.insert(option, "--target=" .. target)
            end
            ---@type boolean
            local support = compiler.has_flags("cxx", table.concat(option, " "))
            local message = "checking for march ... "
            cprint(message .. (support and "${color.success}" or "${color.failure}") .. march)
            if not support then
                if arch ~= "default" then
                    raise(string.format([[The toolchain doesn't support the arch "%s"]], march))
                end
                option = ""
            else
                option = option[1]
            end
        else
            option = nil -- 未探测，设置为nil在下次进行探测
        end
    else
        option = ""
    end

    -- 更新缓存
    cache_info["march"] = option
    _update_cache(cache_info)
    return option
end

---获取rtlib选项
---@return string | nil --rtlib选项
function get_rtlib_option()
    local config = get_config("rtlib")
    return (_is_clang() and config ~= "default") and "-rtlib=" .. config or nil
end

---获取unwindlib选项
---@return string | nil --unwindlib选项
function get_unwindlib_option()
    local config = get_config("unwindlib")
    local force = config:startswith("force")
    local lib = force and string.sub(config, 7, #config) or config
    local option = config ~= "default" and "-unwindlib=" .. lib or nil
    return (_is_clang() and (force or get_config("rtlib") == "compiler-rt")) and option or nil
end

---将mode映射为cmake风格
---@param mode string --xmake风格编译模式
---@return string | nil --cmake风格编译模式
function get_cmake_mode(mode)
    ---@type map_t
    local table = { debug = "Debug", release = "Release", minsizerel = "MinSizeRel", releasedbg = "RelWithDebInfo" }
    return table[mode]
end
