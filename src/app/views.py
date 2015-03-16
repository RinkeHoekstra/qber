# -*- coding: utf-8 -*-
from flask import render_template, g, request, jsonify, make_response, redirect, url_for, abort
from werkzeug.http import parse_accept_header
import logging
import requests
import json
import os
from SPARQLWrapper import SPARQLWrapper, JSON
from rdflib import Graph

import config
import util.sparql_client as sc

from app import app

import loader.reader
import datacube.converter

log = app.logger
log.setLevel(logging.DEBUG)


dataset = config.dataset
dataset_file = config.dataset_file


@app.route('/')
def index():
    return render_template('base.html')

@app.route('/metadata')
def metadata():
    adapter = loader.reader.go(dataset_file,0)
    
    variables = adapter.get_header()
    metadata = adapter.get_metadata()
    examples = adapter.get_examples()
    short_metadata = {metadata.keys()[0]: metadata[metadata.keys()[0]]}
    
    dimensions = get_lsd_dimensions()
    schemes = get_schemes()
    
    data = {
        'variables': variables,
        'metadata': metadata,
        'examples': examples,
        'dimensions': dimensions,
        'schemes': schemes
    }
    
    return jsonify(data)
    
@app.route('/menu',methods=['POST'])
def menu():
    req_json = request.get_json(force=True)
    # log.debug(request.form)
    # req_json = json.loads(request.form.get(0))
    log.debug(req_json)

    items = req_json['items']
    log.debug(items)
    # items = request.form.get('items')
    
    return render_template('menu.html',items=items)
    
    # , variables=variables, metadata=metadata, examples=examples, dimensions=json.dumps(dimensions), schemes=json.dumps(schemes))

@app.route('/variable',methods=['POST'])
def variable():
    req_json = request.get_json(force=True)
    log.debug(req_json)
    
    variable_id = req_json['id']
    description = req_json['description']
    examples = req_json['examples']
    
    log.debug(examples)
    
    return render_template('variable.html',id=variable_id,description=description,examples=examples)
    
    
@app.route('/dimension',methods=['GET'])
def dimension():
    uri = request.args.get('uri', False)
    
    if uri :
        success, visited = sc.resolve(uri, depth=2)
        print "Resolved ", visited
        if success: 
            query = """
                PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
                PREFIX dct: <http://purl.org/dc/terms/>
                PREFIX qb: <http://purl.org/linked-data/cube#>

                SELECT (<{URI}> as ?uri) ?type ?description ?measured_concept WHERE {{
                    OPTIONAL
                    {{
                        <{URI}>   rdfs:comment ?description .
                    }}
                    OPTIONAL
                    {{
                        <{URI}>   a  qb:DimensionProperty .
                        BIND(qb:DimensionProperty AS ?type ) 
                    }}
                    OPTIONAL
                    {{
                        <{URI}>   qb:concept  ?measured_concept . 
                    }}
                    OPTIONAL
                    {{
                        <{URI}>   a  qb:MeasureProperty .
                        BIND(qb:MeasureProperty AS ?type ) 
                    }}
                    OPTIONAL
                    {{
                        <{URI}>   a  qb:AttributeProperty .
                        BIND(qb:AttributeProperty AS ?type ) 
                    }}
                }}
            
            """.format(URI=uri)
            
            results = sc.sparql(query)
            # Turn into something more manageable, and take only the first element.
            variable_definition = sc.dictize(results)[0]

            query = """
                PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
                PREFIX dct: <http://purl.org/dc/terms/>
                PREFIX qb: <http://purl.org/linked-data/cube#>

                SELECT ?type ?measured_concept ?concept ?notation ?label WHERE {{
                      <{URI}>   a               qb:CodedProperty .
                      BIND(qb:DimensionProperty AS ?type )  
                      <{URI}>   qb:codeList     ?cl .
                      {{
                          ?cl       a               skos:ConceptScheme .
                          ?concept  skos:inScheme   ?cl .
                      }} UNION {{
                          ?cl   a               skos:Collection .
                          ?cl   skos:member+    ?concept .
                      }}
                      ?concept    skos:notation       ?notation .
                      ?concept    skos:prefLabel      ?label .
                }}""".format(URI=uri)
            
            codelist_results = sc.sparql(query)
            if len(codelist_results) > 0 :
                codelist = sc.dictize(codelist_results)
                variable_definition['codelist'] = codelist
            
            return jsonify(variable_definition)
            
            
        else :
            return 'error'

        
    else :
        return 'error'
        
    

@app.route('/save',methods=['POST'])
def save():
    req_json = request.get_json(force=True)
    
    variables = req_json['variables']
    
    graph = datacube.converter.data_structure_definition(dataset, variables)
    
    query = sc.make_update(graph)
    result = sc.sparql_update(query)
    
    return result


def get_lsd_dimensions():
    dimensions_response = requests.get("http://amp.ops.few.vu.nl/data.json")
    
    try :
        dimensions = json.loads(dimensions_response.content)
    except :
        log.error("Dimensions could not be loaded from service...")
        
        dimensions = []
        
    return dimensions

def get_schemes():
    if os.path.exists('metadata/schemes.json'):
        log.debug("Loading schemes from file...")
        with open('metadata/schemes.json','r') as f:
            schemes_json = f.read()
        
        schemes = json.loads(schemes_json)
        return schemes
    else :
        log.debug("Loading schemes from RDF sources")
        schemes = []
    
        ### ---
        ### Querying the LOD Cloud
        ### ---
        log.debug("Querying LOD Cloud")

        query = """
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
            PREFIX dct: <http://purl.org/dc/terms/>

            SELECT DISTINCT ?scheme ?label WHERE {
              ?c skos:inScheme ?scheme .
              ?scheme rdfs:label ?label . 
            } 
        """
    
        sparql = SPARQLWrapper('http://lod.openlinksw.com/sparql')
        sparql.setReturnFormat(JSON)
        sparql.setQuery(query)
    
        results = sparql.query().convert()
    
        for r in results['results']['bindings']:
            scheme = {}
        
            scheme['label'] = r['label']['value']
            scheme['uri'] = r['scheme']['value']
            schemes.append(scheme)
        
        log.debug("Found {} schemes".format(len(schemes)))
        ### ---
        ### Querying the HISCO RDF Specification (will become a call to a generic CLARIAH Vocabulary Portal thing.)
        ### ---
        log.debug("Querying HISCO RDF Specification")
    
        query = """
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
            PREFIX dct: <http://purl.org/dc/terms/>

            SELECT DISTINCT ?scheme ?label WHERE {
              ?scheme a skos:ConceptScheme.
              ?scheme dct:title ?label . 
            } 
        """
    
        g = Graph()
        g.parse('metadata/hisco.ttl', format='turtle')
    
        results = g.query(query)
        
        for r in results:
            scheme = {}
            scheme['label'] = r.label
            scheme['uri'] = r.scheme
            schemes.append(scheme)
        
        log.debug("Found a total of {} schemes".format(len(schemes)))
    
        schemes_json = json.dumps(schemes)
    
        with open('metadata/schemes.json','w') as f:
            f.write(schemes_json)
    
        return schemes
        
    
