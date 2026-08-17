/* The response schema, kept in its own file so it can be checked in isolation.
 *
 * Anthropic's structured outputs accept a strict subset of JSON Schema. Two
 * rules bit us and are worth stating plainly, because both fail as an opaque
 * 400 with the schema echoed back:
 *
 *   - No union types. `{type: ["string","null"]}` is rejected; use anyOf, or
 *     design the union away (we use "" instead of null).
 *   - `additionalProperties` may only be `false`, never a schema. That makes a
 *     freeform {field: value} map inexpressible — hence values-as-an-array.
 *
 * Also required: every object sets additionalProperties:false explicitly, and
 * `required` lists every property.
 */

export function schemaFor(calculators){
  return {
    type: "object",
    properties: {
      calculator: {type: "string", enum: calculators},
      confidence: {type: "string", enum: ["high", "medium", "low"]},
      values: {
        type: "array",
        items: {
          type: "object",
          properties: {
            field:     {type: "string"},
            value:     {type: "string"},
            predicted: {type: "boolean"},
            why:       {type: "string"},
          },
          required: ["field", "value", "predicted", "why"],
          additionalProperties: false,
        },
      },
      unclear: {type: "string"},
    },
    required: ["calculator", "confidence", "values", "unclear"],
    additionalProperties: false,
  };
}

/** Walk a schema and report anything the strict subset rejects. */
export function illegal(node, path = "$", found = []){
  if(!node || typeof node !== "object") return found;
  if(Array.isArray(node.type))
    found.push(`${path}.type is a union [${node.type}] — use anyOf`);
  if("additionalProperties" in node && node.additionalProperties !== false)
    found.push(`${path}.additionalProperties is a schema — may only be false`);
  if(node.type === "object" && !("additionalProperties" in node))
    found.push(`${path} is an object without additionalProperties:false`);
  if(node.type === "object" && node.properties){
    const req = new Set(node.required || []);
    for(const k of Object.keys(node.properties)){
      if(!req.has(k)) found.push(`${path}.${k} is not in "required"`);
      illegal(node.properties[k], `${path}.${k}`, found);
    }
  }
  for(const k of ["minimum","maximum","multipleOf","minLength","maxLength"])
    if(k in node) found.push(`${path}.${k} is not supported`);
  if(node.items) illegal(node.items, `${path}[]`, found);
  return found;
}
