"""
Graph Service Module
====================
This module handles graph database operations using Neo4j:
- Course relationships and prerequisites
- Skills mapping
- Specialization paths
- Graph data ingestion

وحدة خدمة الرسم البياني
=======================
هذه الوحدة تتعامل مع عمليات قاعدة بيانات الرسم البياني باستخدام Neo4j:
- علاقات المقررات والمتطلبات السابقة
- ربط المهارات
- مسارات التخصصات
- إدخال بيانات الرسم البياني
"""

import os
from neo4j import GraphDatabase
from fastapi import HTTPException
from typing import List, Dict, Any

# ------------------------------------------------------------
# إعدادات الاتصال بـ Neo4j / Neo4j Connection Settings
# ------------------------------------------------------------
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://graph-db:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
if not NEO4J_PASSWORD:
    raise RuntimeError(
        "NEO4J_PASSWORD environment variable is required. "
        "يرجى ضبط المتغير NEO4J_PASSWORD قبل تشغيل الخدمة."
    )


def get_neo4j_driver():
    """
    Create connection to Neo4j database.
    / إنشاء اتصال بقاعدة بيانات Neo4j.
    
    Returns:
        Neo4j driver instance or None if connection fails
        / مثيل سائق Neo4j أو None إذا فشل الاتصال
    """
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        driver.verify_connectivity()
        return driver
    except Exception as e:
        print(f"Error connecting to Neo4j: {e}")
        return None


# ------------------------------------------------------------
# وظائف الخدمة / Service Functions
# ------------------------------------------------------------

def ingest_graph_data():
    """
    Ingest initial data for specializations, courses, and skills into Neo4j.
    / إدخال البيانات الأولية للتخصصات والمقررات والمهارات في Neo4j.
    
    Returns:
        Dictionary with ingestion results / قاموس يحتوي على نتائج الإدخال
    """
    driver = get_neo4j_driver()
    if not driver:
        raise HTTPException(status_code=500, detail="Could not connect to Neo4j database.")

    specializations_data = [
        {"id": "AI_DS", "name": "Artificial Intelligence & Data Science"},
        {"id": "SE", "name": "Software Engineering"},
        {"id": "IS", "name": "Information Security"},
    ]

    courses_data = [
        {"code": "CS101", "name": "Intro to Programming", "skills": ["Python", "Problem Solving"], "specialization_id": "SE"},
        {"code": "AI300", "name": "Intro to AI", "skills": ["Machine Learning", "Logic"], "specialization_id": "AI_DS"},
        {"code": "DS310", "name": "Data Science", "skills": ["Data Analysis", "Statistics"], "specialization_id": "AI_DS"},
        {"code": "NLP401", "name": "Natural Language Processing", "skills": ["Text Processing", "Transformers"], "specialization_id": "AI_DS"},
        {"code": "SEC200", "name": "Network Security", "skills": ["Cryptography", "Firewalls"], "specialization_id": "IS"},
    ]

    try:
        with driver.session() as session:
            # إنشاء القيود
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (s:Specialization) REQUIRE s.id IS UNIQUE")
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (c:Course) REQUIRE c.code IS UNIQUE")
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (sk:Skill) REQUIRE sk.name IS UNIQUE")

            # إدخال التخصصات
            for spec in specializations_data:
                session.run("MERGE (s:Specialization {id: $id}) SET s.name = $name", id=spec['id'], name=spec['name'])

            # إدخال المقررات والمهارات والعلاقات
            for course in courses_data:
                session.run("MERGE (c:Course {code: $code}) SET c.name = $name", code=course['code'], name=course['name'])
                
                # ربط المقرر بالتخصص
                session.run("""
                    MATCH (c:Course {code: $code})
                    MATCH (s:Specialization {id: $spec_id})
                    MERGE (c)-[:BELONGS_TO]->(s)
                """, code=course['code'], spec_id=course['specialization_id'])

                # ربط المقرر بالمهارات
                for skill_name in course['skills']:
                    session.run("MERGE (sk:Skill {name: $name})", name=skill_name)
                    session.run("""
                        MATCH (c:Course {code: $code})
                        MATCH (sk:Skill {name: $skill_name})
                        MERGE (c)-[:TEACHES]->(sk)
                    """, code=course['code'], skill_name=skill_name)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error ingesting graph data: {repr(e)}")
    finally:
        driver.close()

    return {
        "status": "success",
        "message": f"Graph database populated with {len(specializations_data)} specializations and {len(courses_data)} courses."
    }

def get_skills_for_course(course_code: str) -> List[str]:
    """
    Retrieve skills taught by a specific course.
    / استرجاع المهارات التي يدرسها مقرر معين.
    
    Args:
        course_code: Course code / رمز المقرر
        
    Returns:
        List of skill names / قائمة أسماء المهارات
    """
    try:
        driver = get_neo4j_driver()
        if not driver:
            return []
        
        query = """
        MATCH (c:Course {code: $code})-[:TEACHES]->(sk:Skill)
        RETURN sk.name AS skill
        """
        
        with driver.session() as session:
            result = session.run(query, code=course_code.upper())
            skills = [record["skill"] for record in result if record.get("skill")]
        
        driver.close()
        return skills
    except Exception as e:
        print(f"Error getting skills for course {course_code}: {e}")
        return []

def get_courses_by_skill(skill_name: str) -> List[str]:
    """
    Retrieve courses that teach a specific skill.
    / استرجاع المقررات التي تدرس مهارة معينة.
    
    Args:
        skill_name: Name of the skill / اسم المهارة
        
    Returns:
        List of course names / قائمة أسماء المقررات
    """
    driver = get_neo4j_driver()
    if not driver:
        return []
    
    query = """
    MATCH (sk:Skill {name: $skill_name})<-[:TEACHES]-(c:Course)
    RETURN c.name AS course
    """
    
    with driver.session() as session:
        result = session.run(query, skill_name=skill_name)
        courses = [record["course"] for record in result]
    
    driver.close()
    return courses

def get_specialization_courses(spec_id: str) -> List[Dict[str, Any]]:
    """
    Retrieve courses belonging to a specific specialization.
    / استرجاع المقررات التي تنتمي لتخصص معين.
    
    Args:
        spec_id: Specialization ID / معرف التخصص
        
    Returns:
        List of course dictionaries with code and name / قائمة قواميس المقررات مع الرمز والاسم
    """
    driver = get_neo4j_driver()
    if not driver:
        return []
    
    query = """
    MATCH (s:Specialization {id: $spec_id})<-[:BELONGS_TO]-(c:Course)
    RETURN c.code AS code, c.name AS name
    """
    
    with driver.session() as session:
        result = session.run(query, spec_id=spec_id)
        courses = [{"code": record["code"], "name": record["name"]} for record in result]
    
    driver.close()
    return courses
