/**
 * One Dark 语法高亮主题 -- 用于 prism-react-renderer
 */

import type { PrismTheme } from "prism-react-renderer";

export const oneDarkTheme: PrismTheme = {
  plain: {
    color: "#abb2bf",
    backgroundColor: "#282c34",
  },
  styles: [
    {
      types: ["comment"],
      style: { color: "rgb(92, 99, 112)", fontStyle: "italic" },
    },
    {
      types: ["keyword", "operator", "selector", "changed"],
      style: { color: "rgb(198, 120, 221)" },
    },
    {
      types: ["constant", "number", "builtin", "attr-name"],
      style: { color: "rgb(209, 154, 102)" },
    },
    {
      types: ["char", "symbol"],
      style: { color: "rgb(86, 182, 194)" },
    },
    {
      types: ["variable", "tag", "deleted"],
      style: { color: "rgb(224, 108, 117)" },
    },
    {
      types: ["string", "inserted"],
      style: { color: "rgb(152, 195, 121)" },
    },
    {
      types: ["punctuation"],
      style: { color: "rgb(92, 99, 112)" },
    },
    {
      types: ["function"],
      style: { color: "rgb(97, 175, 239)" },
    },
    {
      types: ["class-name"],
      style: { color: "rgb(229, 192, 123)" },
    },
  ],
};
