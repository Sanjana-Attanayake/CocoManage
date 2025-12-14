from deepface import DeepFace
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from concurrent.futures import ThreadPoolExecutor
import datetime
import pytz
import os

class Attendance():
    current_year = None
    current_month = None
    current_day = None
    current_time = None
    today_attendance_count = 0
    last_recorded_attendance = None
    main_dir = 'media'
    registry_dir = 'registry'

    # Cache for embeddings to avoid recomputing them
    embeddings_cache = {}

    # Function to initialize current date and time
    def init_date_time(self):
        current_date = datetime.datetime.now(pytz.timezone('Asia/Colombo'))
        self.current_year = current_date.year
        self.current_month = current_date.strftime("%B")
        self.current_day = current_date.day
        self.current_time = current_date.strftime("%H:%M:%S")

        # There is a weird bug where the first day of the month corrupt the DB structure
        # The dictionary gets converted to a list and crash the rest of the code
        # To remove it and maintain consistency of data a 0 is added to dates < 10
        if current_date.day < 10:
            self.current_day = "0" + str(current_date.day)
    

    # Function to clear existing captures in the temp folder
    def clear_temp_folder(self, main_dir, temp_dir):
        # Remove the existing files in the temp folder
        for file in os.listdir(os.path.join(main_dir, temp_dir)):
            folder_path = os.path.join(main_dir, temp_dir)
            file_path = os.path.join(folder_path, file)
            os.unlink(file_path)


    # Function to save the uploaded file to the temp folder
    def save_uploaded_file(self, request, main_dir, temp_dir):
        file = request.FILES['photo']
        file_path = os.path.join(temp_dir, file.name)
        default_storage.save(file_path, ContentFile(file.read()))
        uploaded_file_path = os.path.join(main_dir, temp_dir, file.name)
        return uploaded_file_path
    

    # Function to compute the embedding of the uploaded image file
    def compute_embedding(self, file_path):
        # Compute or fetch the cached embedding for a file.
        if file_path in self.embeddings_cache:
            return self.embeddings_cache[file_path]
        try:
            embedding = DeepFace.represent(img_path=file_path, model_name="Facenet512")
            self.embeddings_cache[file_path] = embedding
            return embedding
        
        except Exception as e:
            print(f"Error computing embedding for {file_path}: {e}")
            return None


    # Function to verify the employee
    # def verify_employee(self, uploaded_file_path):
        file_paths = [
            os.path.join(self.main_dir, self.registry_dir, file)
            for file in os.listdir(os.path.join(self.main_dir, self.registry_dir))
        ]

        # Compute the embedding for the uploaded file once
        uploaded_embedding = self.compute_embedding(uploaded_file_path)

        if uploaded_embedding is None:
            print("Failed to compute uploaded image embedding.")
            return None

        identified_emp = None
        dissimilarity_index = float('inf')

        def verify(file_path):
            # Verification for a single file.
            try:
                result = DeepFace.verify(
                    img1_path=file_path,
                    img2_path=uploaded_file_path,
                    model_name="Facenet512",
                    detector_backend="retinaface",
                    distance_metric="euclidean_l2",
                    align=True,
                    enforce_detection=True
                )

                return file_path, result
            
            except Exception as e:
                print(f"Error verifying {file_path}: {e}")
                return file_path, None

        # Run verification in parallel
        with ThreadPoolExecutor(max_workers=8) as executor:
            results = executor.map(verify, file_paths)

        for file_path, result in results:
            if result and result["distance"] < dissimilarity_index and result["verified"]:
                dissimilarity_index = result["distance"]
                identified_emp = os.path.basename(file_path).split(".")[0]

        return identified_emp
    
    # # Function to verify the employee
    def verify_employee(self, uploaded_file_path):
        identified_emp = None
        dissimilarity_index = 1
        
        # Read all files in the directory at once
        file_paths = []
        for file in os.listdir(os.path.join(self.main_dir, self.registry_dir)):
            file_path = os.path.join(self.main_dir, self.registry_dir, file)
            file_paths.append(file_path)

        for file_path in file_paths:
            # Verify the employee from Deepface image recognition 
            try:
                # According to Deepface documentation Facenet512, retinaface and euclidean_l2 output the most accurate results
                result = DeepFace.verify(img1_path=file_path, 
                                         img2_path=uploaded_file_path, 
                                         model_name="Facenet512", 
                                         detector_backend="ssd", 
                                         distance_metric="euclidean_l2", 
                                         align=True, 
                                         enforce_detection=True)
                
                # print(file, result["verified"], result["distance"])
                if result["distance"] < dissimilarity_index and result["verified"] == True:
                    dissimilarity_index = result["distance"]
                    identified_emp = file.split(".")[0]

            except Exception as e:
                print(e)

        return identified_emp
    

    # Function to save attendance to database
    def record_attendance(self, database_obj, emp_no):
        # Initialize the current date and time
        self.init_date_time()

        # Reference to the specific location in the database and append the attendance  
        att_table = database_obj.child("Attendance").child(str(self.current_year)).child(self.current_month).child(emp_no)
        att_table.child(str(self.current_day)).set(self.current_time)


    # Function to get attendance per day (emp no, name, time, tot_attendance_per month)
    def get_attendance_per_day(self, database_obj):
        # dictionary to store the attendance details
        att_dict = {}

        # Initialize the current date and time
        self.init_date_time()

        att_table = database_obj.child("Attendance").child(self.current_year).child(self.current_month).get()
        i = 0
        if att_table.each() != None:
            for att in att_table.each():
                emp_no = att.key()
                tot_att_per_month = len(att.val())
                today_time = att.val().get(str(self.current_day))

                emp_table = database_obj.child("Employee").child(att.key()).get()
                emp_name = emp_table.val().get("name")

                if today_time != None:
                    att_dict[i] = {"emp_no": emp_no, "emp_name": emp_name, "today_time": today_time, "tot_att_per_month": tot_att_per_month}
                    i += 1
                    
        return att_dict
    

    # Function to get today attendance count
    def get_today_attendance(self, database_obj):
        # Initialize the current date and time
        self.init_date_time()

        att_table = database_obj.child("Attendance").child(self.current_year).child(self.current_month).get()
        present_count = 0
        last_updated_datetime = None
        
        if att_table.each() != None:
            for att in att_table.each():
                today_time = att.val().get(str(self.current_day))

                if today_time != None:
                    present_count += 1
                    last_updated_datetime = f'{self.current_year}-{self.current_month}-{self.current_day} {today_time}'
                    
        self.today_attendance_count = present_count
        self.last_recorded_attendance = last_updated_datetime

        return (self.today_attendance_count, self.last_recorded_attendance)