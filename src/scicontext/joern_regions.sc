// Select source-rooted method ASTs and their direct boundary edges before JSON export.
// Joern owns parsing and dataflow. This query does not infer scientific semantics.
import io.shiftleft.codepropertygraph.generated.Cpg
import io.shiftleft.codepropertygraph.generated.nodes.StoredNode
import io.shiftleft.semanticcpg.language.*
import java.nio.file.{Files, Path, Paths}

@main def exec(cpgFile: String, regionsFile: String, outFile: String,
               maxNodes: Int = 4000, maxEdges: Int = 20000) = {
  val graph = Cpg.withStorage(Paths.get(cpgFile), false)
  try {
    val requests = ujson.read(Files.readString(Path.of(regionsFile)))("regions").arr
    val selected = scala.collection.mutable.LinkedHashMap.empty[Long, StoredNode]
    val selectedMethods = scala.collection.mutable.ArrayBuffer.empty[ujson.Value]
    val omissions = scala.collection.mutable.ArrayBuffer.empty[ujson.Value]
    val seenMethods = scala.collection.mutable.Set.empty[Long]
    val paths = scala.collection.mutable.Map.empty[Long, String]
    val allowed = Set("AST", "ARGUMENT", "RECEIVER", "REF", "CALL", "REACHING_DEF",
                      "CFG", "CDG", "CONDITION", "TRUE_BODY", "FALSE_BODY", "PARAMETER_LINK")
    val selectedEdges = scala.collection.mutable.LinkedHashMap.empty[(Long, Long, String, String), flatgraph.Edge]
    for (request <- requests) {
      val file = request("path").str
      val start = request("start_line").num.toInt
      val end = request("end_line").num.toInt
      val methods = graph.method.filenameExact(file).filter(m =>
        m.lineNumber.exists(_ <= start) && m.lineNumberEnd.exists(_ >= end)).toList
        .sortBy(m => (m.lineNumberEnd.get - m.lineNumber.get, -m.lineNumber.get, m.id))
      methods.headOption match {
        case None => omissions += ujson.Obj("request" -> request, "reason" -> "no_enclosing_method")
        case Some(method) if !seenMethods.contains(method.id) =>
          seenMethods += method.id
          val body = method.ast.toList
          val ids = body.map(_.id).toSet + method.id
          val touching = (body :+ method).iterator.flatMap(n =>
            new flatgraph.traversal.NodeMethods(n).bothE).filter(e => allowed.contains(e.label)).toVector
            .distinctBy(e => (e.src.id, e.dst.id, e.label, e.propertyMaybe.toString))
          val endpoints = touching.flatMap(e => Seq(e.src, e.dst)).map(_.asInstanceOf[StoredNode])
          val additions = (body :+ method) ++ endpoints
          val keys = touching.map(e => (e.src.id, e.dst.id, e.label, e.propertyMaybe.toString))
          if ((selected.keySet.toSet ++ additions.map(_.id)).size > maxNodes ||
              (selectedEdges.keySet.toSet ++ keys).size > maxEdges) {
            omissions += ujson.Obj("request" -> request, "method_id" -> method.id.toString,
                                   "reason" -> "whole_method_exceeds_export_budget")
          } else {
            additions.foreach(n => selected.update(n.id, n))
            body.foreach(n => paths.update(n.id, file))
            touching.zip(keys).foreach((edge, key) => selectedEdges.update(key, edge))
            selectedMethods += ujson.Obj("id" -> method.id.toString, "path" -> file,
              "name" -> method.fullName, "start_line" -> method.lineNumber.get.toInt,
              "end_line" -> method.lineNumberEnd.get.toInt,
              "node_ids" -> ujson.Arr.from(ids.toList.sorted.map(_.toString)))
          }
        case _ => ()
      }
    }
    def value(x: Any): ujson.Value = x match {
      case null => ujson.Null
      case b: Boolean => ujson.Bool(b)
      case n: java.lang.Number => ujson.Num(n.doubleValue)
      case s: String => ujson.Str(s)
      case other => ujson.Str(other.toString)
    }
    val propertyNames = Set("CODE", "NAME", "FULL_NAME", "METHOD_FULL_NAME", "TYPE_FULL_NAME",
      "SIGNATURE", "IS_EXTERNAL", "ARGUMENT_INDEX", "ARGUMENT_NAME", "CONTROL_STRUCTURE_TYPE",
      "ORDER", "DISPATCH_TYPE", "EVALUATION_STRATEGY",
      "FILENAME", "LINE_NUMBER", "LINE_NUMBER_END", "COLUMN_NUMBER", "COLUMN_NUMBER_END")
    val vertices = selected.values.toList.sortBy(_.id).map { node =>
      val props = ujson.Obj.from(node.properties.filter((key, _) => propertyNames.contains(key))
        .map((key, v) => key -> value(v)))
      paths.get(node.id).foreach(path => props("FILENAME") = ujson.Str(path))
      ujson.Obj("id" -> node.id.toString, "label" -> node.label, "properties" -> props)
    }
    val links = selectedEdges.values.toList.map { edge =>
      val props = ujson.Obj()
      edge.propertyName.zip(edge.propertyMaybe).foreach((name, v) => props(name) = value(v))
      ujson.Obj("outV" -> edge.src.id.toString, "inV" -> edge.dst.id.toString,
                "label" -> edge.label, "properties" -> props)
    }
    val result = ujson.Obj("vertices" -> ujson.Arr.from(vertices), "edges" -> ujson.Arr.from(links),
      "selection" -> ujson.Obj("methods" -> ujson.Arr.from(selectedMethods),
        "omissions" -> ujson.Arr.from(omissions), "overlays" -> ujson.Arr.from(graph.metaData.overlays.l),
        "max_nodes" -> maxNodes, "max_edges" -> maxEdges,
        "policy" -> "smallest_enclosing_method_ast_and_direct_boundary"))
    Files.writeString(Path.of(outFile), ujson.write(result, -1, false, true))
  } finally graph.close()
}
