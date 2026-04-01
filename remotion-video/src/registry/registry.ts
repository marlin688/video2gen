/**
 * 组件注册表
 *
 * 管理 Schema × Style 映射，支持动态注册、查找、fallback。
 */

import type {
  SchemaName,
  StyleMeta,
  RegistryEntry,
  StyleComponentProps,
} from "./types";
import type React from "react";

class ComponentRegistry {
  private entries = new Map<string, RegistryEntry>();
  private defaults = new Map<SchemaName, string>(); // schema → default style id

  /**
   * 注册一个 style 组件。
   * id 前缀必须匹配 meta.schema（如 "slide.tech-dark" 对应 schema "slide"）。
   */
  register<S extends SchemaName>(
    meta: StyleMeta & { schema: S },
    component: React.ComponentType<StyleComponentProps<S>>,
  ): void {
    const prefix = meta.id.split(".")[0];
    if (prefix !== meta.schema) {
      throw new Error(
        `Style id "${meta.id}" 前缀 "${prefix}" 与 schema "${meta.schema}" 不匹配`,
      );
    }

    this.entries.set(meta.id, {
      meta,
      component: component as React.ComponentType<StyleComponentProps>,
    });

    if (meta.isDefault) {
      this.defaults.set(meta.schema, meta.id);
    }
  }

  /** 按 style id 精确查找 */
  resolve(styleId: string): RegistryEntry | undefined {
    return this.entries.get(styleId);
  }

  /** 获取某个 schema 的默认 style */
  resolveDefault(schema: SchemaName): RegistryEntry | undefined {
    const defaultId = this.defaults.get(schema);
    return defaultId ? this.entries.get(defaultId) : undefined;
  }

  /**
   * 为一个 segment 解析组件。
   *
   * 优先级：
   * 1. segment.component 字段（显式指定 style id）
   * 2. material type fallback（向后兼容旧 script.json）
   */
  resolveForSegment(
    segment: { component?: string; material?: string },
    hasRecording: boolean,
  ): RegistryEntry | undefined {
    // 1. 显式指定
    if (segment.component) {
      const entry = this.resolve(segment.component);
      if (entry) return entry;
      // 找不到指定 style，fallback 到该 schema 的 default
      const schema = segment.component.split(".")[0] as SchemaName;
      return this.resolveDefault(schema);
    }

    // 2. material fallback
    switch (segment.material) {
      case "A":
        return this.resolveDefault("slide");
      case "B":
        return hasRecording
          ? this.resolveDefault("recording")
          : this.resolveDefault("terminal");
      case "C":
        return this.resolveDefault("source-clip");
      default:
        return this.resolveDefault("slide");
    }
  }

  /** 生成 LLM prompt 用的组件列表 markdown 表格 */
  toLLMPromptTable(): string {
    const rows: string[] = [];
    rows.push("| 组件 ID | 适用场景 | 标签 |");
    rows.push("|---------|---------|------|");

    const sorted = Array.from(this.entries.values())
      .filter((e) => !e.meta.deprecated)
      .sort((a, b) => a.meta.id.localeCompare(b.meta.id));

    for (const entry of sorted) {
      const tags = entry.meta.tags?.join(", ") || "";
      const def = entry.meta.isDefault ? " (默认)" : "";
      rows.push(
        `| \`${entry.meta.id}\`${def} | ${entry.meta.description} | ${tags} |`,
      );
    }
    return rows.join("\n");
  }

  /** 获取所有条目 */
  getAll(): RegistryEntry[] {
    return Array.from(this.entries.values());
  }

  /** 获取所有非废弃条目 */
  getActive(): RegistryEntry[] {
    return Array.from(this.entries.values()).filter(
      (e) => !e.meta.deprecated,
    );
  }
}

/** 全局单例 */
export const registry = new ComponentRegistry();
