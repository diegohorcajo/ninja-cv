import json
import traceback
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from gemini_api import GeminiAPI
import os
import dotenv
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

apikey = os.getenv("GEMINI_API_KEY")

# Crear instancia global (o se la pasamos a la clase)
gemini = GeminiAPI(api_key=apikey)


class CVMatcher:
    # posibles modelos:
    # all-MiniLM-L6-v2
    # paraphrase-MiniLM-L3-v2
    # TaylorAI/bge-micro-v2
    def __init__(self, model_name="TaylorAI/bge-micro-v2"):
        self.model   = None
        self.model_name = model_name
        self.cv_data = None
        self.offer_data = None


    def _load_model(self):
        from sentence_transformers import SentenceTransformer
        # Esta función carga el modelo solo si no ha sido cargado antes
        if self.model is None:
            print("Loading SentenceTransformer model for the first time...")
            self.model = SentenceTransformer(self.model_name)
            print("Model loaded successfully.")

    # ----------- 1. Sector -----------
    def preprocess_sector(self, sector):
        # Primero, manejamos el caso de que sea una lista
        if isinstance(sector, list):
            # Nos aseguramos de que cada elemento de la lista sea un string antes de unir
            processed_list = [str(s).lower().strip() for s in sector]
            output = " and ".join(processed_list)
        else:
            # Para todo lo demás (str, int, float, None), lo convertimos a string PRIMERO
            output = str(sector).lower().strip().replace(",", " and")
        
        return f"principal job sector: {output}"

    def sector_similarity(self, offer_dict, cv_dict):
        offer_sector = offer_dict.get("sector", "")
        cv_sector = cv_dict.get("primary_sector", "")
        
        if not offer_sector or not cv_sector:
            return 0.0
            
        # Preprocess sectors for better matching
        offer_sector_processed = self.preprocess_sector(offer_sector)
        cv_sector_processed = self.preprocess_sector(cv_sector)
        
        # If sectors are exactly the same after preprocessing
        if offer_sector_processed == cv_sector_processed:
            return 1.0
            
        # Calculate semantic similarity
        try:
            cv_emb, offer_emb = self.model.encode([cv_sector_processed, offer_sector_processed])
            sim_score = cosine_similarity([offer_emb], [cv_emb])[0][0]
            
            # Add a small boost to the score
            sim_score = min(1.0, sim_score + 0.1)
            return sim_score
            
        except Exception as e:
            print(f"Error calculating sector similarity: {e}")
            return 0.5  # Default similarity in case of error


    # ----------- 2. Educación -----------
    def preprocess_field(self, field):
            #Forzamos la conversión a string ANTES de hacer cualquier otra cosa
            return f"field of study: {str(field).lower().strip().replace(',', ' and')}"


    def education_similarity(self, offer_dict, cv_education):
        self._load_model()
        offer_field = self.preprocess_field(offer_dict['education']['field'])
        cv_field    = self.preprocess_field(cv_education['field'])
        offer_emb, cv_emb = self.model.encode([offer_field, cv_field])
        sim_score = cosine_similarity([offer_emb], [cv_emb])[0][0] + 0.05
        return float(min(1, sim_score))



    def education_final_score(self, offer_dict, cv_dict):
        self._load_model()
        # Get minimum education level from offer and ensure it's a float
        min_education = float(offer_dict.get('education', {}).get('number', 0))
        
        # Get all education entries from CV
        cv_education = cv_dict.get('education', [])
        
        if not cv_education:
            return 0.0
            
        # Find the highest education level in CV, ensuring all are floats
        highest_cv_edu = max([float(edu.get('number', 0)) for edu in cv_education])
        
        # If highest CV education is below minimum required
        if highest_cv_edu < min_education:
            return 0.0
            
        # Calculate base similarity with the closest matching education
        best_similarity = float(0)
        same_level_edu = None
        
        for edu in cv_education:
            edu_level = float(edu.get('number', 0))
            if edu_level >= min_education:
                similarity = self.education_similarity(offer_dict, edu)
                if similarity > best_similarity:
                    best_similarity = similarity
                    if edu_level == min_education:
                        same_level_edu = edu
        
        # Calculate addon for higher education
        higher_education = [edu for edu in cv_education if float(edu.get('number', 0)) > min_education]
        addon = 0.0
        
        for edu in higher_education:
            edu_level = float(edu.get('number', 0))
            level_diff = edu_level - min_education
            similarity = self.education_similarity(offer_dict, edu)
            addon += 0.1 * level_diff * similarity
        
        # Cap the final score at 1.0
        return min(1.0, best_similarity + addon)


    # ----------- 3. Skills -----------
    def skills_similarity(self, offer_dict, cv_dict, type="technical"):
        self._load_model()
        if type == "technical":
            cv_skills = [s.lower() for s in cv_dict.get("technical_abilities", [])]
            offer_skills = [s.lower() for s in offer_dict.get("technical_abilities", [])]
        elif type == "soft":
            cv_skills = [s.lower() for s in cv_dict.get("soft_skills", [])]
            offer_skills = [s.lower() for s in offer_dict.get("soft_skills", [])]
        else:
            return {}, 0

        if not offer_skills or not cv_skills:
            return {}, 0

        cv_embeddings = self.model.encode(cv_skills)
        offer_embeddings = self.model.encode(offer_skills)

        # Calculate similarity for each offer skill against all CV skills
        skill_similarities = {}
        for i, offer_skill in enumerate(offer_skills):
            if offer_skill in cv_skills:
                # Exact match
                skill_similarities[offer_skill] = 1.0
            else:
                # Semantic similarity
                sim_scores = cosine_similarity([offer_embeddings[i]], cv_embeddings)[0]
                max_sim = np.max(sim_scores)
                skill_similarities[offer_skill] = min(1, max_sim + 0.1)

        avg_similarity = np.mean(list(skill_similarities.values())) if skill_similarities else 0
        return skill_similarities, avg_similarity


    # ----------- 4. Experiencia en el rol -----------
    def role_similarity(self, offer_role, cv_roles):
        self._load_model()
        cv_embeddings    = self.model.encode(cv_roles)
        offer_embedding  = self.model.encode(offer_role)
        return cosine_similarity([offer_embedding], cv_embeddings)[0]

    def role_experience_similarity(self, offer_dict, cv_dict):
        self._load_model()
        total_experience = 0
        role_similarities = []
        
        # Extract all roles and their years of experience from CV
        cv_experience = []
        for experience in cv_dict.get('experience', []):
            for role in experience.get('roles', []):
                position = role.get('position', '')
                years = float(role.get('years', 0))
                if position and years > 0:
                    cv_experience.append({
                        'position': position,
                        'years': years,
                        'company': experience.get('company', ''),
                        'duration': experience.get('duration', '')
                    })
        
        if not cv_experience:
            return 0, 0, 0, 0
            
        # Calculate similarity for each role
        cv_roles = [exp['position'] for exp in cv_experience]
        offer_role = offer_dict.get("role", "")
        
        if not offer_role:
            return 0, 0, 0, 0
            
        role_similarities = self.role_similarity(offer_role, cv_roles)
        
        # Calculate weighted experience
        weighted_experience = 0
        for i, exp in enumerate(cv_experience):
            similarity = role_similarities[i]
            weighted_experience += similarity * exp['years']
            
        # Get min and max experience from offer
        min_exp = float(offer_dict.get('experience', {}).get('min', 0.0))
        max_exp = float(offer_dict.get('experience', {}).get('max',  9999.0))  # Default range if max not specified
        
        # Calculate experience percentage (capped at 1.0)
        if min_exp > 0:
            experience_perc = min(1.0, weighted_experience / min_exp)
        else:
            experience_perc = 1.0 if weighted_experience > 0 else 0
            
        return min_exp, max_exp, weighted_experience, experience_perc


    # ----------- 5. Creación del diccionario -----------

    def final_score(self, offer_path, cv_path):
        self._load_model()
        """
        Calculate final matching scores between an offer and a CV.
        
        Args:
            offer_path (str): Path to the job offer file
            cv_path (str): Path to the CV file
            
        Returns:
            dict: Dictionary containing all matching scores and details
        """
        # Parse the offer and CV
        offer_dict = gemini.parse_offer(offer_path)
        cv_dict = gemini.parse_cv(cv_path)
        
        # Return the complete matching results
        return self.create_dict(offer_dict, cv_dict)




    def create_dict(self, offer_dict, cv_dict):
        self._load_model()
        # Get technical skills with similarity scores
        tech_skills_dict, tech_score = self.skills_similarity(offer_dict, cv_dict, "technical")
        soft_skills_dict, soft_score = self.skills_similarity(offer_dict, cv_dict, "soft")
        
        # Process technical skills - check if we should show top/bottom or all
        tech_skills = {}
        if tech_skills_dict:
            sorted_tech = sorted(tech_skills_dict.items(), key=lambda x: x[1], reverse=True)
            if len(sorted_tech) >= 6:
                tech_skills = {
                    'top_matches': [skill for skill, _ in sorted_tech[:3]],
                    'bottom_matches': [skill for skill, _ in sorted_tech[-3:]]
                }
            else:
                tech_skills = {
                    'title': 'Technical skills similarity order',
                    'skills': [skill for skill, _ in sorted_tech]
                }
        
        # Process soft skills - check if we should show top/bottom or all
        soft_skills = {}
        if soft_skills_dict:
            sorted_soft = sorted(soft_skills_dict.items(), key=lambda x: x[1], reverse=True)
            if len(sorted_soft) >= 6:
                soft_skills = {
                    'top_matches': [skill for skill, _ in sorted_soft[:3]],
                    'bottom_matches': [skill for skill, _ in sorted_soft[-3:]]
                }
            else:
                soft_skills = {
                    'title': 'Soft skills similarity order',
                    'skills': [skill for skill, _ in sorted_soft]
                }
        
        # Get role experience details
        min_exp, max_exp, total_exp, exp_score = self.role_experience_similarity(offer_dict, cv_dict)
        role = offer_dict.get("role", "")

        # --- NUEVA LÓGICA CLARA Y ROBUSTA PARA EL TEXTO DE EXPERIENCIA ---
        min_exp_raw = offer_dict.get('experience', {}).get('min', 0)
        max_exp_raw = offer_dict.get('experience', {}).get('max', 9999.0)
        
        # Convert to float for consistent comparison
        min_exp = float(min_exp_raw) if min_exp_raw is not None else 0
        max_exp = float(max_exp_raw) if max_exp_raw is not None else 9999.0
        
        experience_requirement_text = ""
        # Caso 1: No se especifica experiencia mínima o es 0.
        if min_exp == 0:
            experience_requirement_text = "There's not any experience required for this role."
        # Caso 2: Se especifica un mínimo pero no un máximo (o máximo muy alto).
        elif max_exp >= 9999.0:
            experience_requirement_text = f"The offer is looking for someone with more than {int(min_exp)} years of experience."
        # Caso 3: Se especifican ambos, mínimo y máximo.
        else:
            experience_requirement_text = f"The offer is looking for between {int(min_exp)} and {int(max_exp)} years of experience."

        full_explanation = f"You have approximately {round(total_exp, 1)} years of experience in roles similar to '{role}'. {experience_requirement_text}"
        
        # Get sector information
        sector_similarity = self.sector_similarity(offer_dict, cv_dict)
        offer_sector = offer_dict.get("sector", "")
        cv_sector = cv_dict.get("primary_sector", "")
        
        # Get education information
        education_score = self.education_final_score(offer_dict, cv_dict)
        min_education = float(offer_dict.get("education", {}).get("number", 0))
        min_education_level = offer_dict.get("education", {}).get("min", "No especificado")
        min_education_field = offer_dict.get("education", {}).get("field", "No especificado")
        
        # Get candidate's education and find the highest degree
        cv_education_list = cv_dict.get("education", [])
        highest_cv_degree = None
        if cv_education_list:
            sorted_cv_education = sorted(cv_education_list, key=lambda x: float(x.get('number', 0)), reverse=True)
            highest_cv_degree = sorted_cv_education[0]

        education_details = {}
        education_explanation = ""

        # SCENARIO 1: The offer does NOT specify a minimum education level
        if min_education == 0:
            education_explanation = "The offer does not specify a minimum education level. The candidate's highest degree is shown for reference."
            education_details = {
                "minimum_required_level": "Not specified",
                "minimum_required_field": min_education_field if min_education_field != "No especificado" else "Not specified",
                # USAMOS LAS CLAVES ORIGINALES para no romper el HTML
                "equivalent_level_cv": highest_cv_degree.get('degree', 'Not available') if highest_cv_degree else 'Not available',
                "equivalent_field_cv": highest_cv_degree.get('field', 'Not available') if highest_cv_degree else 'Not available',
                # Devolvemos una lista vacía, el JS lo mostrará como 'None'
                "higher_education_degrees": [],
                "meets_requirement": True 
            }
        # SCENARIO 2: The offer DOES specify a minimum education level
        else:
            same_level_education = [edu for edu in cv_education_list if float(edu.get('number', 0)) == min_education]
            higher_education = [edu for edu in cv_education_list if float(edu.get('number', 0)) > min_education]

            match_text = "The candidate meets the minimum requirement." if same_level_education or higher_education else "The candidate does not meet the minimum requirement."
            education_explanation = f"The offer requires at least {min_education_level}. {match_text}"
            
            # Find the most relevant degree to show as "equivalent"
            equivalent_education = same_level_education[0] if same_level_education else (highest_cv_degree if higher_education else {})
            
            education_details = {
                "minimum_required_level": min_education_level,
                "minimum_required_field": min_education_field,
                "equivalent_level_cv": equivalent_education.get('degree', 'Not available'),
                "equivalent_field_cv": equivalent_education.get('field', 'Not available'),
                "higher_education_degrees": [edu.get('degree', '') for edu in higher_education],
                "meets_requirement": education_score >= 0.5
            }

        # Format the final return dictionary with all the processed information
        result = {
            "technical_skills_score": int(np.round(100 * tech_score, 2)),
            "soft_skills_score": int(np.round(100 * soft_score, 2)),
            "role_experience_score": int(np.round(100 * exp_score, 2)),
            "education_score": int(np.round(100 * education_score, 2)),
            "sector_score": int(np.round(100 * sector_similarity, 2)),
            
            "technical_skills": tech_skills,
            "soft_skills": soft_skills,
            
            "role_experience": {
                "explanation": full_explanation,  # Usamos la variable que acabamos de crear
                "details": {
                    "role": role, "min_years": min_exp, "max_years": max_exp, "total_experience": round(total_exp, 1)
                }
            },
            
            "education": {
                "explanation": education_explanation,
                "details": education_details
            },
            
            "sector": {
                "explanation": f"The offer's sector is '{offer_sector}' and your main sector is '{' and '.join(cv_sector) if isinstance(cv_sector, list) else cv_sector}'. "
                              f"The similarity between both sectors is {round(sector_similarity * 100, 1)}%.",
                "details": {
                    "offer_sector": offer_sector, "cv_sector": ' and '.join(cv_sector) if isinstance(cv_sector, list) else cv_sector, "similarity": round(sector_similarity * 100, 1)
                }
            }
        }
        
        return result


# instanciamos la clase
matcher = CVMatcher()

    

